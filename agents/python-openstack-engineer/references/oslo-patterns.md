# Oslo Library Patterns Reference

> **Scope**: oslo.config, oslo.messaging, oslo.db, oslo.log, oslo.policy usage in OpenStack services.
> **Version range**: oslo.config 9.x+, oslo.messaging 14.x+, oslo.db 14.x+, oslo.log 5.x+
> **Generated**: 2026-04-09

---

## Pattern Table

| Library | Correct Entry Point | Version | Avoid |
|---------|---------------------|---------|-------|
| `oslo_config` | `from oslo_config import cfg; CONF = cfg.CONF` | 9.0+ | `from oslo.config import cfg` (old namespace) |
| `oslo_messaging` | `import oslo_messaging as messaging` | 14.0+ | Direct AMQP client construction |
| `oslo_db` | `from oslo_db import api as oslo_db_api` | 14.0+ | Raw `sqlalchemy.create_engine` without oslo session mgmt |
| `oslo_log` | `from oslo_log import log as logging` | 5.0+ | `import logging` directly |
| `oslo_policy` | `from oslo_policy import policy` | 4.0+ | Custom RBAC without oslo_policy enforcer |

---

## Correct Patterns

### oslo.config — Option Registration

Register before `CONF()` is called. Group by service component.

```python
from oslo_config import cfg

_opts = [
    cfg.StrOpt('transport_url', default='rabbit://guest:guest@localhost:5672/', help='Oslo messaging transport URL.'),
    cfg.IntOpt('workers', default=1, min=1, help='API worker processes.'),
    cfg.BoolOpt('debug', default=False, help='Enable debug logging.'),
]

CONF = cfg.CONF
CONF.register_opts(_opts, group='myservice')
workers = CONF.myservice.workers
```

`oslo-config-generator` introspects registered opts for sample configs. Unregistered options are invisible to tooling.

---

### oslo.log — Structured Logger Setup

```python
from oslo_log import log as logging
from oslo_config import cfg

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

def setup_logging(project_name: str) -> None:
    logging.setup(CONF, project_name)
    logging.set_defaults(default_log_levels=logging.get_default_log_levels())

LOG.info('Processing request %(req_id)s for user %(user_id)s',
         {'req_id': context.request_id, 'user_id': context.user_id})
```

`logging.setup()` wires oslo.log into oslo.config, enabling `log_file`, `log_dir`, `debug` flags.

---

### oslo.messaging — RPC Client Pattern

```python
import oslo_messaging as messaging
from oslo_config import cfg

class MyServiceAPI:
    RPC_API_VERSION = '1.3'

    def __init__(self):
        transport = messaging.get_rpc_transport(CONF)
        target = messaging.Target(topic='myservice', version=self.RPC_API_VERSION)
        self._client = messaging.get_rpc_client(transport, target)

    def create_resource(self, context, name: str, properties: dict):
        cctxt = self._client.prepare(version='1.1')
        return cctxt.call(context, 'create_resource', name=name, properties=properties)

    def notify_resource_deleted(self, context, resource_id: str):
        cctxt = self._client.prepare(version='1.0')
        cctxt.cast(context, 'resource_deleted', resource_id=resource_id)
```

`prepare(version='1.1')` enables version negotiation during rolling upgrades.

---

### oslo.db — Database Session

```python
from oslo_db.sqlalchemy import enginefacade

context_manager = enginefacade.transaction_context()
context_manager.configure(connection=CONF.database.connection)

@enginefacade.writer
def create_resource(context, values: dict):
    ref = models.Resource()
    ref.update(values)
    context.session.add(ref)
    return ref

@enginefacade.reader
def get_resource(context, resource_id: str):
    return (context.session.query(models.Resource)
            .filter_by(id=resource_id, deleted=False).first())
```

`enginefacade.writer`/`reader` manage transaction lifecycles and enable read/write splitting.

---

## Pattern Catalog

### Use oslo_log Instead of Direct logging Import

**Detection**:
```bash
grep -rn '^import logging$' --include="*.py"
grep -rn 'logging\.getLogger' --include="*.py" | grep -v "oslo_log\|# noqa"
```

Bypasses oslo.log integration — no context fields, no runtime log level changes via `CONF.debug`.

**Preferred action**: `from oslo_log import log as logging`

---

### Load Transport URL from oslo.config

**Detection**:
```bash
grep -rn 'rabbit://\|amqp://' --include="*.py" | grep -v "# example\|\.cfg\|test"
```

Transport URL must come from `CONF.transport_url` to be overridable in deployment configs.

**Preferred action**: `transport = messaging.get_rpc_transport(CONF)`

---

### Use oslo.db enginefacade for Database Sessions

**Detection**:
```bash
grep -rn 'create_engine\|sessionmaker' --include="*.py" | grep -v "enginefacade\|migration\|test"
```

Bypasses oslo.db retry logic, connection pool management, and `sqlite+pysqlite:///:memory:` test override.

**Preferred action**: `enginefacade.writer`/`reader` decorators.

---

### Enforce oslo.policy on Every API Operation

**Detection**:
```bash
grep -rn 'def (create|update|delete|get|list)_' --include="*.py" -A 10 | grep -v "policy\|enforce"
```

Missing enforcement silently bypasses RBAC.

**Preferred action**:
```python
ENFORCER = policy.Enforcer(CONF)

def delete_resource(self, context, resource_id):
    target = {'project_id': context.project_id}
    ENFORCER.enforce(context, 'myservice:resource:delete', target,
                     do_raise=True, exc=exception.PolicyNotAuthorized,
                     action='myservice:resource:delete')
    return db.resource_delete(context, resource_id)
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `NoSuchOptError` | Option read before `register_opts()` | Move registration before `CONF()` in startup |
| `DuplicateOptError` | `register_opts` called twice | Guard with try/except or use `register_opt` in tests |
| `MessageDeliveryFailure` | Broker unreachable or topic not found | Check `transport_url`, verify queue exists |
| `DBConnectionError` | Database unreachable | Check `CONF.database.connection`, verify DB is up |
| `PolicyNotRegistered` | Rule referenced before registration | Register rules in `policy.py` loaded at startup |

---

## Detection Commands Reference

```bash
grep -rn '^import logging$' --include="*.py"
grep -rn 'rabbit://\|amqp://' --include="*.py" | grep -v "# example\|\.cfg\|test"
grep -rn 'create_engine\|sessionmaker' --include="*.py" | grep -v "enginefacade\|migration\|test"
grep -rn 'def (create|update|delete)_' --include="*.py" -A 5 | grep -v "enforce\|policy"
```

---

## See Also

- `hacking-rules.md` — H-series PEP 8 extensions
- `rpc-versioning.md` — oslo.messaging version negotiation
