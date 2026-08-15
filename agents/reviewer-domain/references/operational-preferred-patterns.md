# Pragmatic Builder Roaster - Operational Corrections

Common operational mistakes, signals, and preferred responses.

## Preferred Pattern: No Rollback Plan

**Signal**:
```bash
docker build -t myapp:latest .
docker-compose down
docker-compose up -d
# No rollback, no previous version tagged
```

**Why it matters**: No time to design rollback at 3 AM. "Revert the commit" ignores migrations, config changes, stateful systems.

**Preferred action**:
```bash
#!/bin/bash
set -e
PREVIOUS_VERSION=$(docker ps --format '{{.Image}}' | grep myapp | head -1)
NEW_VERSION="myapp:$(git rev-parse --short HEAD)"

docker build -t "$NEW_VERSION" .
docker tag "$NEW_VERSION" myapp:latest
docker-compose down
docker-compose up -d

if ! ./health_check.sh; then
    echo "Rolling back to $PREVIOUS_VERSION"
    docker tag "$PREVIOUS_VERSION" myapp:latest
    docker-compose down && docker-compose up -d
    exit 1
fi
echo "To rollback: docker tag $PREVIOUS_VERSION myapp:latest && docker-compose restart"
```

**Verification**: Every deployment has documented rollback. Staging confirms rollback works.

---

## Preferred Pattern: Log Before and After Risky Operations

**Signal**: No logging before external API calls; only logs on success.

**Why it matters**: Cannot reconstruct request flow without correlation IDs. Missing context makes debugging impossible.

**Preferred action**:
```python
def process_payment(user_id, amount):
    correlation_id = generate_correlation_id()
    logging.info("payment_attempt", extra={
        'correlation_id': correlation_id, 'user_id': user_id, 'amount': amount
    })
    try:
        result = external_payment_api.charge(user_id, amount)
        logging.info("payment_result", extra={
            'correlation_id': correlation_id, 'success': result.success,
            'transaction_id': result.transaction_id
        })
        return result
    except Exception as e:
        logging.error("payment_failed", extra={
            'correlation_id': correlation_id, 'user_id': user_id,
            'error': str(e), 'error_type': type(e).__name__
        }, exc_info=True)
        raise
```

**Verification**: Logs before each external call. Error handlers include correlation ID and context.

---

## Preferred Pattern: Test Boundary and Failure Cases

**Signal**: Tests only cover happy path.

**Why it matters**: Edge cases always happen in production. Users send empty carts, negative numbers, null values.

**Preferred action**:
```python
def calculate_discount(cart_total, discount_percent):
    if cart_total < 0:
        raise ValueError("Cart total cannot be negative")
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount must be between 0 and 100")
    return cart_total * (discount_percent / 100)

def test_calculate_discount_edge_cases():
    assert calculate_discount(100, 10) == 10.0
    assert calculate_discount(0, 10) == 0.0
    assert calculate_discount(100, 0) == 0.0
    assert calculate_discount(100, 100) == 100.0
    with pytest.raises(ValueError):
        calculate_discount(-100, 10)
    with pytest.raises(ValueError):
        calculate_discount(100, 150)
```

**Verification**: Boundaries covered (0, max, negative, null). Error paths have dedicated assertions.

---

## Preferred Pattern: Circuit Breaker for External Dependencies

**Signal**: No protection against failing external service.

**Why it matters**: Every request waits for timeout. Cascading failures exhaust thread pool.

**Preferred action**:
```python
from pybreaker import CircuitBreaker

recommendation_breaker = CircuitBreaker(fail_max=5, timeout_duration=60)

@recommendation_breaker
def fetch_recommendations(user_id):
    return recommendation_service.get(user_id)

def get_user_recommendations(user_id):
    try:
        return fetch_recommendations(user_id)
    except CircuitBreakerError:
        logging.warning(f"Circuit open for user {user_id}, using fallback")
        return get_popular_items()
    except Exception as e:
        logging.error(f"Failed to get recommendations: {e}")
        return get_popular_items()
```

**When to use**: All external service calls, non-critical dependencies.

---

## Preferred Pattern: Validate User Input

**Signal**: No validation or sanitization on request params.

**Why it matters**: SQL injection, XSS, resource exhaustion, no length limits.

**Preferred action**:
```python
@app.route('/search')
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query required'}), 400
    if len(query) > 100:
        return jsonify({'error': 'Query too long'}), 400

    results = db.execute(
        text("SELECT * FROM products WHERE name LIKE :pattern LIMIT 100"),
        {'pattern': f'%{query}%'}
    ).fetchall()
    return jsonify([dict(r) for r in results])
```

**When to use**: All user input at API boundaries.

---

## Preferred Pattern: Async Long-Running Work

**Signal**: Long-running operation blocks request thread.

**Why it matters**: Thread blocked 3+ minutes. HTTP clients timeout. Thread pool exhausted.

**Preferred action**:
```python
@celery.task
def process_video_async(video_id):
    video = download_video(video_id)
    processed = transcode_video(video)
    upload_result(processed)

@app.route('/process-video', methods=['POST'])
def process_video():
    task = process_video_async.delay(request.json['video_id'])
    return jsonify({'status': 'processing', 'task_id': task.id}), 202
```

**When to use**: Operations > 5 seconds, video/image processing, data exports, bulk ops.

---

## Preferred Pattern: Monitoring Before Launch

**Signal**: No metrics, no alerts, no visibility.

**Why it matters**: Cannot diagnose issues. No baseline. Outages go undetected.

**Preferred action**:
```python
from prometheus_client import Counter, Histogram

requests_total = Counter('api_requests_total', 'Total requests', ['endpoint', 'method', 'status'])
request_duration = Histogram('api_request_duration_seconds', 'Duration', ['endpoint'])
```

Set up metrics, logs, traces, alerts during development. Establish baseline before launch.

---

## Preferred Pattern: Named Constants

**Signal**: Magic numbers without explanation (`3`, `300`, `50`).

**Why it matters**: Unclear reasoning. Cannot change without deploy. No per-environment tuning.

**Preferred action**:
```python
class Config:
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL', '300'))  # 5 min for user profiles
    DB_MAX_CONNECTIONS = int(os.getenv('DB_MAX_CONNECTIONS', '50'))
```

**When to use**: All timeouts, retries, limits, thresholds. Document why each value is chosen.

---

## Preferred Pattern: Connection Pooling

**Signal**: New database connection per call.

**Why it matters**: Connection setup is expensive. Hundreds of connections under load. DB rejects after max_connections.

**Preferred action**:
```python
engine = create_engine(
    'postgresql://user:password@localhost/mydb',
    pool_size=20, max_overflow=10, pool_timeout=30,
    pool_recycle=3600, pool_pre_ping=True
)

def get_user(user_id):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM users WHERE id = :user_id"),
            {'user_id': user_id}
        ).fetchone()
```

**When to use**: All database, Redis, and HTTP client connections.
