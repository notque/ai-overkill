# Production Gaps Catalog

Common production readiness gaps with solutions.

## Deployment and Rollback

### No Documented Rollback
**Symptoms**: No rollback docs, team assumes "revert commit," no automated triggers.

**Solution**:
```bash
deploy() {
    echo "To rollback: ./rollback.sh $(git rev-parse HEAD)"
}
rollback_to_commit() {
    git checkout $1 && docker-compose down && docker-compose up -d && ./health_check.sh
}
```
**Prevention**: Write rollback before deploy script. Test in staging. Automate triggers on health check failure.

### Missing Health Checks
**Symptoms**: Deployments complete but app broken. Load balancer sends traffic to unhealthy instances.

**Solution**:
```python
@app.route('/health')
def health_check():
    return {"status": "healthy", "timestamp": time.time()}
# Deploy: ./deploy.sh && curl http://localhost:8000/health || ./rollback.sh
```
**Prevention**: /health and /ready endpoints. Verify DB, cache, external APIs. Integrate with load balancers.

---

## Error Handling

### No Retry for External Calls
**Symptoms**: Transient failures cause complete request failure. No backoff or jitter.

**Solution**:
```python
def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
```
**Prevention**: Wrap all external calls. Exponential backoff with jitter. Circuit breakers. Log retries.

### Silent Background Failures
**Symptoms**: Background tasks fail without notification. Data processing silently stops.

**Solution**:
```python
def process_job(job_id):
    try:
        # job logic
        metrics.increment('jobs.success')
    except Exception as e:
        metrics.increment('jobs.failure')
        logger.error(f"Job {job_id} failed", exc_info=True)
        alert_on_call(f"Critical job failure: {job_id}")
        raise
```
**Prevention**: Emit success/failure metrics. Alert on failure rates. Dead letter queues.

---

## Observability

### No Structured Logging
**Symptoms**: Free-form strings, can't filter by correlation ID, grep through unstructured text.

**Solution**:
```python
# Before: logging.info(f"User {user_id} purchased item {item_id}")
# After:
logging.info("user_purchase", extra={
    'event_type': 'purchase', 'user_id': user_id,
    'item_id': item_id, 'correlation_id': request.correlation_id
})
```
**Prevention**: Structured logging libraries. Correlation IDs everywhere. Standard log fields. Queryable backend.

### Missing Critical Metrics
**Symptoms**: Cannot answer "how many requests failing?" No latency visibility.

**Solution**:
```python
request_count = Counter('api_requests_total', 'Total', ['endpoint', 'status'])
request_duration = Histogram('api_request_duration_seconds', 'Duration', ['endpoint'])
```
**Prevention**: Instrument all endpoints. Track resource usage. Monitor queues. Dashboards before production.

---

## Edge Cases

### No Input Validation
**Symptoms**: Crashes on empty/null/extreme input. Injection vulnerabilities.

**Solution**:
```python
def create_user(username, age):
    if not username or len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    if age < 0 or age > 150:
        raise ValueError("Invalid age")
```
**Prevention**: Validate at API boundaries. Schema validation (Pydantic, JSON Schema). Test edge cases. Sanitize input.

### Race Conditions
**Symptoms**: Occasional data corruption under load. Duplicate records.

**Solution**:
```python
class SafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
    def increment(self):
        with self._lock:
            self._value += 1
        return self._value
```
**Prevention**: Identify shared mutable state. Locks or atomic ops. Test under load. DB constraints.

---

## Scalability

### No Query Optimization
**Symptoms**: Slow pages as data grows. DB CPU at 100%. N+1 queries.

**Solution**:
```sql
CREATE INDEX idx_users_email ON users(email);
-- N+1 fix: JOIN instead of separate queries
SELECT users.*, orders.* FROM users
JOIN orders ON users.id = orders.user_id WHERE users.id IN (1, 2, 3);
```
**Prevention**: Index frequently queried columns. EXPLAIN. Slow query logs. select_related/prefetch_related. Load test with production data.

### No Caching
**Symptoms**: Expensive computations repeated. DB overloaded with identical queries.

**Solution**:
```python
@lru_cache(maxsize=128)
def get_user_profile(user_id):
    return expensive_db_query(user_id)
```
**Prevention**: Cache with TTL. Invalidation strategy. Monitor hit rates. Distributed cache for multi-instance.

---

## Resource Management

### Resource Leaks
**Symptoms**: "Too many open files." Connection pool exhausted. Memory grows.

**Solution**:
```python
# Always use context managers
with open(filepath) as f:
    data = f.read()
```
**Prevention**: Context managers. Connection pool limits. Monitor file descriptors. finally blocks.

### No Rate Limiting
**Symptoms**: Single user overloads API. No DDoS protection.

**Solution**:
```python
@limiter.limit("10 per minute")
def expensive_operation():
    pass
```
**Prevention**: Per-user and per-IP limits. Rate limit expensive ops. 429 with Retry-After. Monitor hit counts.
