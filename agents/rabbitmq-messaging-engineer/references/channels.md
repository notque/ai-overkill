# RabbitMQ Channel Management Reference

> **Scope**: AMQP channel lifecycle, pooling, error recovery. Does not cover connection management or queue topology.
> **Version range**: RabbitMQ 3.8+ (AMQP 0-9-1)
> **Generated**: 2026-04-09

---

## Pattern Table

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| Channel per thread | Multi-threaded producers/consumers | Single-threaded code |
| Channel pool | Short-lived burst publishers | Long-lived consumers (use dedicated) |
| Dedicated consumer channel | `basic_consume` subscribers | Publishing (separate publish/consume) |
| `confirm_select()` | Critical message delivery | High-throughput fire-and-forget (+10-15% latency) |

---

## Correct Patterns

### Channel Per Thread (Python/pika)

Channels are not thread-safe. Each thread must own its own.

```python
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

def producer_thread(routing_key: str, body: bytes) -> None:
    channel = connection.channel()
    channel.confirm_delivery()
    channel.basic_publish(
        exchange='events', routing_key=routing_key, body=body,
        properties=pika.BasicProperties(delivery_mode=2),
    )
    channel.close()
```

---

### Separate Channels for Publish and Consume

```python
publish_channel = connection.channel()
consume_channel = connection.channel()

consume_channel.basic_consume(queue='tasks', on_message_callback=handle_message, auto_ack=False)
publish_channel.basic_publish(exchange='results', routing_key='done', body=result)
```

Mixing on same channel causes head-of-line blocking — slow publish with confirms holds up ack delivery.

---

### Publisher Confirm on Channel (Go/amqp091-go)

```go
ch, err := conn.Channel()
if err != nil {
    return fmt.Errorf("open channel: %w", err)
}
defer ch.Close()

if err := ch.Confirm(false); err != nil {
    return fmt.Errorf("confirm mode: %w", err)
}

confirms := ch.NotifyPublish(make(chan amqp.Confirmation, 1))

err = ch.PublishWithContext(ctx, exchange, routingKey, true, false, amqp.Publishing{
    DeliveryMode: amqp.Persistent,
    Body:         body,
})

select {
case confirm := <-confirms:
    if !confirm.Ack {
        return fmt.Errorf("broker nacked message")
    }
case <-ctx.Done():
    return fmt.Errorf("confirm timeout: %w", ctx.Err())
}
```

---

## Pattern Catalog

### Reuse Channels Across Messages

**Detection**:
```bash
rg 'def.*publish|def.*send' --type py -A 5 | grep 'channel()'
grep -rn '\.channel()' --include="*.py" | grep -v 'self\._channel\|self\.channel'
```

Channel-per-message exhausts the default limit (2047 per connection) and adds round-trip latency per message.

**Preferred action**:
```python
class Publisher:
    def __init__(self, connection):
        self._channel = connection.channel()
        self._channel.confirm_delivery()

    def publish(self, body: bytes) -> None:
        self._channel.basic_publish(
            exchange='events', routing_key='task', body=body,
            properties=pika.BasicProperties(delivery_mode=2),
        )
```

---

### Use One Channel Per Thread

**Detection**:
```bash
grep -rn 'self\._channel\s*=' --include="*.py" -A 1
rg 'go func.*ch\s+\*amqp\.Channel' --type go
```

Concurrent threads on one channel interleave AMQP frames — broker sees malformed frames, closes connection with 505 or 503.

**Preferred action**: One channel per thread, or `pika.SelectConnection` with single IO loop and thread-safe queue.

---

### Drain Confirm Notifications After Publishing

**Detection**:
```bash
rg 'confirm_delivery|Confirm\(false\)' --type py --type go -A 3 | grep -v 'NotifyPublish\|wait_for_confirms'
```

Unread confirms accumulate — after ~1000 unconfirmed messages the channel stalls.

**Preferred action**: `channel.wait_for_confirms_or_die()` after each batch, or handle `basic.return` callbacks.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `CHANNEL_ERROR - expected 'channel.open'` | Channel reused after close | Create new channel |
| `NOT_FOUND - no exchange` | Exchange not declared | `exchange_declare()` before publish |
| `RESOURCE_LOCKED - exclusive access` | Exclusive queue on another connection | Dedicated connection per exclusive queue |
| `PRECONDITION_FAILED - inequivalent arg` | Queue/exchange params differ from existing | `passive=True` to check existing params |
| `ACCESS_REFUSED` | Missing permissions | `rabbitmqctl set_permissions` |
| Channel max reached (503) | Too many channels | Limit per connection; default 2047 |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| RabbitMQ 3.8.0 | Quorum queues GA | `x-queue-type: quorum`; mirrored deprecated |
| RabbitMQ 3.9.0 | `global` flag for `basic.qos` deprecated | `prefetch_count` always per-consumer |
| RabbitMQ 3.12.0 | Classic queue v1 storage removed | Auto-upgrade; check `x-max-length` behavior |
| pika 1.3.0 | `basic_publish` returns `None` not `bool` | Use `confirm_delivery()` instead |
| amqp091-go 1.7.0 | `PublishWithContext` replaces `Publish` | Context-aware for timeout/cancel |

---

## Detection Commands Reference

```bash
rg 'def.*publish' --type py -A 8 | grep '\.channel()'  # Channel churn
grep -rn 'self\._channel\s*=' --include="*.py"           # Shared channel
rg 'confirm_delivery\(\)' --type py -A 20 | grep -L 'wait_for_confirms'  # Undrained confirms
rg 'ch, err := conn.Channel' --type go -A 30 | grep -v 'defer ch.Close()'  # Unclosed Go channels
```

---

## See Also

- `performance.md` — prefetch tuning, connection pool sizing
- `error-handling.md` — publisher confirms flow, consumer ack patterns
