# RabbitMQ Error Handling & Reliability Reference

> **Scope**: Publisher confirms, consumer acknowledgment, dead letter exchanges, retry logic. Not cluster failover or network partitions.
> **Version range**: AMQP 0-9-1 clients; quorum queue notes for RabbitMQ 3.8+
> **Generated**: 2026-04-09

---

## Pattern Table

| Pattern | When Required | Performance Cost |
|---------|---------------|-----------------|
| Publisher confirms | Critical messages (orders, payments, events) | ~10-15% throughput reduction |
| Manual consumer ack | All production consumers | None (`auto_ack=False` default) |
| Dead letter exchange | Any queue where message loss is unacceptable | None at publish time |
| Nack + requeue=False | Poison messages that fail repeatedly | Requires DLX or message is dropped |
| Retry with TTL queue | Transient failures (DB down, network blip) | Extra queue + TTL overhead |

---

## Correct Patterns

### Publisher Confirms (Python/pika)

```python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.confirm_delivery()

try:
    channel.basic_publish(
        exchange='orders',
        routing_key='order.created',
        body=json.dumps(order).encode(),
        properties=pika.BasicProperties(
            delivery_mode=2,       # persistent
            content_type='application/json',
            message_id=str(order['id']),
        ),
        mandatory=True,
    )
except pika.exceptions.UnroutableError:
    log.error("message unroutable — check exchange bindings")
    raise
except pika.exceptions.NackError:
    log.error("broker nacked message — check node health")
    raise
```

Without `confirm_delivery()`, `basic_publish` returns immediately. Broker crash before disk write = message lost.

---

### Consumer Manual Acknowledgment (Python/pika)

```python
def handle_message(channel, method, properties, body):
    try:
        result = process(body)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except TransientError as e:
        log.warning("transient error, requeueing: %s", e)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except PoisonMessageError as e:
        log.error("poison message, rejecting: %s", e)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

channel.basic_qos(prefetch_count=10)
channel.basic_consume(queue='orders', on_message_callback=handle_message)
```

`auto_ack=True` deletes message on delivery. Consumer crash during `process()` = message gone.

---

### Dead Letter Exchange Setup

```python
# 1. Declare the dead letter exchange
channel.exchange_declare(
    exchange='dlx.orders',
    exchange_type='direct',
    durable=True,
)

# 2. Declare the dead letter queue
channel.queue_declare(
    queue='orders.dead',
    durable=True,
    arguments={
        'x-message-ttl': 604_800_000,  # 7 days retention
    }
)
channel.queue_bind(queue='orders.dead', exchange='dlx.orders', routing_key='order.created')

# 3. Declare the main queue with DLX pointer
channel.queue_declare(
    queue='orders',
    durable=True,
    arguments={
        'x-dead-letter-exchange': 'dlx.orders',
        'x-dead-letter-routing-key': 'order.created',
        'x-message-ttl': 3_600_000,
    }
)
```

Without DLX, rejected/expired messages are silently discarded. DLX creates an audit trail and enables replay.

---

### Retry Queue Pattern (Delayed Retry Without Plugin)

```python
# Retry queue: messages expire back to main queue
channel.queue_declare(
    queue='orders.retry',
    durable=True,
    arguments={
        'x-message-ttl': 30_000,                  # 30s retry delay
        'x-dead-letter-exchange': '',              # default exchange
        'x-dead-letter-routing-key': 'orders',
    }
)

def handle_message(channel, method, properties, body):
    retry_count = int(properties.headers.get('x-retry-count', 0)) if properties.headers else 0

    try:
        process(body)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except TransientError:
        if retry_count >= 3:
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        channel.basic_ack(delivery_tag=method.delivery_tag)
        channel.basic_publish(
            exchange='',
            routing_key='orders.retry',
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                headers={'x-retry-count': retry_count + 1},
            ),
        )
```

Avoids `rabbitmq_delayed_message_exchange` plugin. TTL on retry queue acts as delay. Use multiple retry queues with increasing TTLs for exponential backoff.

---

## Pattern Catalog

### Use Manual Ack on Production Consumers

**Detection**:
```bash
grep -rn 'auto_ack\s*=\s*True' --include="*.py"
rg 'basic_consume.*auto_ack=True' --type py
grep -rn 'noAck\s*:\s*true' --include="*.js" --include="*.ts"
rg '\.Consume\(' --type go -A 3 | grep 'autoAck.*true'
```

**Signal**:
```python
channel.basic_consume(queue='orders', on_message_callback=handle_order, auto_ack=True)
```

Message deleted on delivery before `handle_order` starts. Consumer crash = permanent loss.

**Preferred action**: Remove `auto_ack=True` (defaults to `False`), call `channel.basic_ack()` after processing.

---

### Limit Retry Count Before Routing to DLX

**Detection**:
```bash
rg 'basic_nack' --type py -B 5 | grep 'requeue=True'
grep -rn 'basic_reject.*requeue=True' --include="*.py"
rg '\.Nack\(' --type go -A 2 | grep 'true'
```

**Signal**:
```python
except Exception as e:
    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    # Poison message loops: deliver → fail → requeue → deliver
```

Drives consumer CPU to 100%, blocks all other messages.

**Preferred action**: Track retry count in headers. After N retries, `requeue=False` to route to DLX.

---

### Configure a Dead Letter Exchange for Every Production Queue

**Detection**:
```bash
rg 'queue_declare' --type py -A 10 | grep -v 'x-dead-letter-exchange'
rabbitmqctl list_queues name dead_letter_exchange | grep -v '\S\s\S'
```

**Signal**:
```python
channel.queue_declare(queue='payments', durable=True)
# No DLX — rejected/expired messages vanish
```

No audit trail, no replay, no alerting on failures.

**Preferred action**: Always declare DLX for production queues. Route to `{queue}.dead` with 7-day TTL.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `pika.exceptions.UnroutableError` | `mandatory=True` but no queue bound | Declare queue + binding before publishing |
| `pika.exceptions.NackError` | Broker nacked (quorum not reached, disk full) | Check cluster health; `rabbitmqctl cluster_status` |
| `406 PRECONDITION_FAILED` | Queue redeclared with different args | Delete queue and redeclare, or use `passive=True` |
| `404 NOT_FOUND` | Publishing to non-existent exchange/queue | Declare before publishing; check name typo |
| Duplicate messages after restart | Consumer crashed after processing, before acking | Idempotent consumer logic; track processed message IDs |
| DLX queue not receiving rejects | Queue missing `x-dead-letter-exchange` arg | Redeclare queue with DLX argument |
| Messages requeued indefinitely | No retry limit in exception handler | Add retry counter in headers; route to DLX after N retries |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 3.8.0 | Quorum queues support publisher confirms | Confirms now work with quorum queues |
| 3.10.0 | Quorum queues support per-message TTL | `x-message-ttl` header respected on quorum queues |
| 3.13.0 | `consumer_timeout` default 30 minutes | Consumers holding unacked messages >30min get channel closed |
| pika 1.0.0 | `basic_publish` raises exceptions (not return bool) | Update exception handling |
| amqplib (Node) 0.10+ | `channel.nack()` requires explicit `requeue` param | Always pass explicit `requeue` argument |

---

## Detection Commands Reference

```bash
# Auto-ack consumers (Python)
grep -rn 'auto_ack=True' --include="*.py"

# Auto-ack consumers (Node.js)
grep -rn 'noAck: true\|noAck:true' --include="*.ts" --include="*.js"

# Missing DLX on queue declarations
rg 'queue_declare' --type py -A 8 | grep -v 'dead.letter'

# Infinite requeue patterns
rg 'basic_nack|basic_reject' --type py -A 2 | grep 'requeue=True'

# Queues with no DLX configured (live check)
rabbitmqctl list_queues name dead_letter_exchange messages_unacknowledged

# Queues with growing unacked message count
rabbitmqctl list_queues name messages messages_unacknowledged consumers
```

---

## See Also

- `channels.md` — publisher confirm flow at the channel level
- `performance.md` — prefetch tuning to prevent unacked message backlog
