# RabbitMQ Performance Tuning Reference

> **Scope**: Throughput optimization, prefetch tuning, lazy queues, connection pooling. Not cluster hardware sizing or OS-level tuning.
> **Version range**: RabbitMQ 3.8+ for quorum queues; 3.6+ for lazy queues
> **Generated**: 2026-04-09

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `prefetch_count=10-100` | All | CPU-bound consumers | I/O-bound consumers (may need higher) |
| `x-queue-mode: lazy` | 3.6+ | Queue backlog > 1M messages | Low-latency queues (adds ~1-2ms) |
| `x-queue-type: quorum` | 3.8+ | HA required | Single-node dev setup |
| Connection pool (3-10 conns) | All | Multi-threaded producers | Single-threaded scripts |
| Batch ack (`multiple=True`) | All | High-throughput consumers | Low-latency pipelines |

---

## Correct Patterns

### Consumer Prefetch (Python/pika)

```python
channel = connection.channel()
channel.basic_qos(prefetch_count=20)
channel.basic_consume(queue='tasks', on_message_callback=handle_message, auto_ack=False)
```

`prefetch_count=0` (default) pushes all messages to first consumer. Others starve.

**Tuning**: Start at 1, increase. CPU-bound: 2-10. I/O-bound: 20-100. Monitor: `rabbitmqctl list_consumers`.

---

### Lazy Queues for Large Backlogs (3.6+)

```python
channel.queue_declare(
    queue='bulk-tasks',
    durable=True,
    arguments={
        'x-queue-mode': 'lazy',
        'x-message-ttl': 86400000,
        'x-max-length': 10_000_000,
        'x-overflow': 'reject-publish',
    }
)
```

Default queues keep messages in memory. 10M message backlog = 10+ GB RAM → memory alarms. Lazy queues write to disk immediately, capping memory to ~1 MB per queue.

---

### Connection Pooling (Go)

```go
type Pool struct {
    connections []*amqp.Connection
    mu          sync.Mutex
    idx         int
}

func NewPool(dsn string, size int) (*Pool, error) {
    p := &Pool{connections: make([]*amqp.Connection, size)}
    for i := range size {
        conn, err := amqp.Dial(dsn)
        if err != nil {
            return nil, fmt.Errorf("dial[%d]: %w", i, err)
        }
        p.connections[i] = conn
    }
    return p, nil
}

func (p *Pool) Get() *amqp.Connection {
    p.mu.Lock()
    defer p.mu.Unlock()
    conn := p.connections[p.idx%len(p.connections)]
    p.idx++
    return conn
}
```

Each AMQP connection = TCP socket. Connection-per-publish at 1000 msg/s = 5000-10000 RTTs/s of overhead. Pool of 5 reduces to zero. 3-10 connections for most workloads.

---

### Batch Consumer Ack

```python
def handle_message(ch, method, properties, body):
    process(body)
    ch.basic_ack(delivery_tag=method.delivery_tag, multiple=True)
```

Each `basic_ack` is an AMQP frame. At 10,000 msg/s, `multiple=True` cuts ack overhead by 5-10x. Trade-off: consumer crash requeues all unacked messages.

---

## Pattern Catalog

### Set Prefetch Count Before Consuming

**Detection**:
```bash
grep -rn 'basic_qos' --include="*.py" | grep 'prefetch_count=0'
rg 'basic_consume' --type py -B 10 | grep -v 'basic_qos'
rg '\.Consume\(' --type go -B 10 | grep -v 'Qos\('
```

**Signal**:
```python
channel.basic_consume(queue='tasks', on_message_callback=handle)
# No basic_qos — unlimited prefetch
```

First consumer hoards all messages. Others get nothing. Under spike load: OOM kills.

**Preferred action**: Always `channel.basic_qos(prefetch_count=N)` before `basic_consume`. Start with 10.

---

### Set Message TTL on Persistent Queues

**Detection**:
```bash
rg 'queue_declare' --type py -A 5 | grep -v 'x-message-ttl\|ttl'
rabbitmqctl list_queues name policy | grep -v 'ttl\|expire'
```

**Signal**:
```python
channel.queue_declare(queue='notifications', durable=True)
# No TTL, no max-length — grows forever
```

Memory alarm fires at 40% watermark, blocking all publishers.

**Preferred action**:
```python
channel.queue_declare(
    queue='notifications',
    durable=True,
    arguments={
        'x-message-ttl': 3_600_000,
        'x-max-length': 1_000_000,
        'x-overflow': 'reject-publish',
        'x-dead-letter-exchange': 'dlx',
    }
)
```

---

### Migrate to Quorum Queues for HA

**Detection**:
```bash
rabbitmqctl list_policies | grep 'ha-mode'
rg 'ha-mode|ha_mode' --type py --type go --type js
```

**Signal**:
```bash
rabbitmqctl set_policy ha-all ".*" '{"ha-mode":"all"}' --apply-to queues
```

Classic mirrored queues use synchronous replication. Under >10K msg/s, mirrors fall behind → `slave_not_synchronized` → failover loses messages. Deprecated 3.11, removed 4.0.

**Preferred action**:
```python
channel.queue_declare(
    queue='critical-tasks',
    durable=True,
    arguments={'x-queue-type': 'quorum'},
)
```

Quorum queues require 3.8+ and 3-node cluster minimum.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `AMQP connection heartbeat timeout` | Consumer blocked; no heartbeat | Reduce `prefetch_count`; process in separate thread |
| `Memory alarm on node rabbit@host` | Queue backlog exceeds `vm_memory_high_watermark` | Enable lazy queues; add consumers; add nodes |
| `Disk alarm on node rabbit@host` | Disk free below `disk_free_limit` | Add disk; enable lazy queues; purge stale queues |
| `basic.return` / mandatory unroutable | No queue bound to exchange+routing key | Check bindings with `rabbitmqctl list_bindings` |
| Consumer utilization < 50% | Prefetch too low or slow processing | Increase `prefetch_count`; add consumer instances |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 3.6.0 | Lazy queues (`x-queue-mode: lazy`) | Use for bulk/batch queues |
| 3.8.0 | Quorum queues GA | Replace mirrored queues |
| 3.9.0 | `global` QoS flag deprecated | `basic_qos` always per-consumer |
| 3.10.0 | Quorum queue message TTL | TTL now supported on quorum queues |
| 3.11.0 | Classic mirrored queues deprecated | Migrate before 4.0 |
| 3.12.0 | Classic queues v2 storage default | 20-30% less memory |
| 4.0.0 | Classic mirrored queues removed | `ha-mode` policies fail |

---

## Detection Commands Reference

```bash
# Prefetch 0 (unlimited) consumers
grep -rn 'prefetch_count=0' --include="*.py"
rg 'basic_consume' --type py -B 15 | grep -v 'basic_qos'

# Queues without TTL
rabbitmqctl list_queues name arguments | grep -v 'x-message-ttl'

# Classic mirrored policies (deprecated)
rabbitmqctl list_policies | grep 'ha-mode'

# Consumer utilization (management API)
curl -u guest:guest http://localhost:15672/api/consumers | python3 -m json.tool | grep utilisation

# Queue memory usage
rabbitmqctl list_queues name memory messages consumers
```

---

## See Also

- `channels.md` — channel lifecycle and per-thread patterns
- `error-handling.md` — publisher confirms, DLX, retry logic
