# OpenStack RPC Versioning Reference

> **Scope**: oslo.messaging RPC API version negotiation for rolling upgrades. Does not cover REST API microversioning.
> **Version range**: oslo.messaging 14.x+, OpenStack 2023.x+
> **Generated**: 2026-04-09

---

## Version Negotiation Model

```
Client (new node)        Transport        Server (old node)
     |                      |                    |
     | prepare(version='1.5')|                    |
     |--------------------> |                    |
     |                      | version_cap=1.3    |
     |  RPCVersionCapError   |                    |
     | <------------------  |                    |
```

- `RPC_API_VERSION` on manager = server's maximum
- `version_cap` on client = client's declared maximum
- `prepare(version=X)` = what this specific call requires

---

## Pattern Table

| Scenario | Version Bump | Server Change | Client Change |
|----------|-------------|---------------|---------------|
| New optional argument | Minor (`1.2` -> `1.3`) | Accept new arg with default | `prepare(version='1.3')` |
| New required method | Minor (`1.2` -> `1.3`) | Add method | `prepare(version='1.3')` |
| Remove argument | Major (`1.x` -> `2.0`) | New major series | Both sides update |
| Change argument type | Major (`1.x` -> `2.0`) | New major series | Incompatible change |

---

## Correct Patterns

### Server Side — Versioned RPC Manager

```python
class MyServiceManager(manager.Manager):
    RPC_API_VERSION = '1.4'
    target = messaging.Target(version=RPC_API_VERSION)

    def create_resource(self, context, name, properties=None):
        """Available since 1.0. `properties` added in 1.2."""
        if properties is None:
            properties = {}
        return db.resource_create(context, name, properties)

    def resize_resource(self, context, resource_id, new_size, preserve_data=False):
        """Added in 1.4."""
        return db.resource_resize(context, resource_id, new_size, preserve_data)
```

---

### Client Side — Version-Pinned Calls

```python
class MyServiceAPI:
    RPC_API_VERSION = '1.4'

    def __init__(self):
        transport = messaging.get_rpc_transport(CONF)
        target = messaging.Target(topic='myservice', version=self.RPC_API_VERSION)
        self._client = messaging.get_rpc_client(transport, target)

    def create_resource(self, context, name):
        """Works against servers >= 1.0."""
        cctxt = self._client.prepare(version='1.0')
        return cctxt.call(context, 'create_resource', name=name)

    def create_resource_with_props(self, context, name, properties):
        """Requires server >= 1.2."""
        cctxt = self._client.prepare(version='1.2')
        return cctxt.call(context, 'create_resource', name=name, properties=properties)

    def resize_resource(self, context, resource_id, new_size, preserve_data=False):
        """Requires server >= 1.4."""
        cctxt = self._client.prepare(version='1.4')
        return cctxt.call(context, 'resize_resource',
                          resource_id=resource_id, new_size=new_size, preserve_data=preserve_data)
```

---

### Version Cap During Upgrades

```python
cfg.StrOpt(
    'rpc_current_version',
    default=None,
    help='RPC API version cap. Set to old version during upgrade, unset when all nodes upgraded.',
),

def __init__(self):
    transport = messaging.get_rpc_transport(CONF)
    version_cap = CONF.myservice.rpc_current_version or self.RPC_API_VERSION
    target = messaging.Target(
        topic='myservice', version=self.RPC_API_VERSION, version_cap=version_cap,
    )
    self._client = messaging.get_rpc_client(transport, target)
```

---

## Pattern Catalog

### Bump Version When Changing Method Signature

**Detection**:
```bash
git diff HEAD~1 HEAD -- '*.py' | grep -E '^\+.*def (create|update|delete|get|list)_.*context' | head -20
git diff HEAD~1 HEAD -- '*.py' | grep 'RPC_API_VERSION'
```

Old nodes calling without new args crash with `TypeError`. Bump version, make new args optional.

---

### Pin Version Before Calling New Methods

**Detection**:
```bash
grep -rn 'cctxt\.call\|cctxt\.cast' --include="*.py" -B 2 | grep -v "prepare"
```

`_client.call()` without `.prepare(version=X)` sends no version requirement. Server on older version fails with `MethodNotFound`.

---

### Keep RPC_API_VERSION Current

**Detection**:
```bash
grep -rn "RPC_API_VERSION = '1\.0'" --include="*.py"
```

Never-changed version with added methods means clients can't use `prepare(version=X)` for protection.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `MessagingTimeout` | Exceeds `rpc_response_timeout` (60s default) | Increase timeout or use cast |
| `RPCVersionCapError` | Client version > server cap | Set `version_cap`, or upgrade server first |
| `NoSuchMethod` | Method not on server | Check version pins; server may be running older code |
| `TypeError: unexpected keyword argument` | New arg sent to old server | `prepare(version=X)` where X introduced the arg |

---

## Detection Commands Reference

```bash
grep -rn 'cctxt\.call\|cctxt\.cast' --include="*.py" -B 3 | grep -v "prepare"
grep -rn "RPC_API_VERSION" --include="*.py"
git diff -- '*.py' | grep '^[+-].*def .*context'
grep -rn "rpc_current_version\|version_cap" --include="*.py" --include="*.cfg"
```

---

## See Also

- `oslo-patterns.md` — oslo.messaging transport and client setup
- `hacking-rules.md` — Code style for RPC handler code
