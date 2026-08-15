# OpenStack Hacking Rules Reference

> **Scope**: H-series PEP 8 extensions enforced by `hacking` package. Does not cover standard PEP 8.
> **Version range**: hacking 6.x+ (flake8 5.x+, tox -e pep8)
> **Generated**: 2026-04-09

---

## Rule Summary Table

| Rule | What It Checks | Severity |
|------|---------------|----------|
| H201 | No bare `except:` | Hard block |
| H202 | No `except Exception:` without re-raise | Warning |
| H301 | No `import` of multiple modules per line | Hard block |
| H302 | No full module import when `from … import` available | Warning |
| H303 | No wildcard imports | Hard block |
| H304 | No relative imports | Hard block |
| H306 | Alphabetical order within import groups | Warning |
| H401 | No docstring starting with a space | Warning |
| H501 | No `%s` formatting with `locals()` or `self.__dict__` | Hard block |
| H701 | No i18n import from old `oslo.i18n` namespace | Hard block |
| H903 | No Windows line endings | Hard block |

---

## Correct Patterns

### H201 — Specific Exception Handling

```python
try:
    result = nova_client.servers.get(server_id)
except nova_exceptions.NotFound:
    raise exception.ServerNotFound(server_id=server_id)
except nova_exceptions.ClientException as exc:
    LOG.error('Nova API error: %s', exc)
    raise

# Exception acceptable when re-raising
try:
    do_risky_thing()
except Exception:
    LOG.exception('Unexpected error')
    raise
```

---

### H301/H303/H304 — Import Conventions

One per line, no wildcards, no relative paths, ordered stdlib -> third-party -> project.

```python
import os
import sys

from oslo_config import cfg
from oslo_log import log as logging

from myservice import exception
from myservice.db import api as db_api
from myservice import utils
```

---

### H501 — No locals()/self.__dict__ in % formatting

```python
LOG.error('Server %(server_id)s not found in zone %(zone)s',
          {'server_id': server_id, 'zone': zone})
LOG.info('Created resource %s', resource.id)
```

---

### H701 — i18n Import from New Namespace

```python
from myservice.i18n import _
raise exception.ResourceNotFound(msg=_('Resource %s not found') % res_id)
```

---

## Pattern Catalog

### H201: Name the Exception Class

**Detection**:
```bash
grep -rn 'except:' --include="*.py"
rg 'except:\s*$' --type py
```

**Preferred action**:
```python
try:
    result = db.get_resource(context, resource_id)
except exception.ResourceNotFound:
    LOG.warning('Resource %s not found', resource_id)
    return None
```

---

### H303: Import Only What You Use

**Detection**:
```bash
grep -rn 'from .* import \*' --include="*.py"
```

**Preferred action**: `from oslo_config.cfg import CONF, StrOpt, IntOpt`

---

### H304: Use Absolute Imports

**Detection**:
```bash
grep -rn 'from \.' --include="*.py" | grep -v "test\|#"
```

OpenStack enforces absolute imports. Relative imports break `oslo-config-generator`, tox, and Zuul.

**Preferred action**: `from myservice.common.utils import format_id`

---

### H501: Use Explicit Dict for % Formatting

**Detection**:
```bash
grep -rn 'locals()\|self\.__dict__' --include="*.py" | grep '%'
```

`locals()` captures entire scope including sensitive values.

**Preferred action**:
```python
LOG.debug('State: %s timeout: %s', self.state, self.timeout)
```

---

## Error-Fix Mappings

| `tox -e pep8` Output | Rule | Fix |
|----------------------|------|-----|
| `H201 no 'except:'` | H201 | Specific exception class |
| `H303 no wildcard imports` | H303 | Explicit names |
| `H304 No relative imports` | H304 | `from myservice.utils` |
| `H306 imports not alphabetical` | H306 | Sort within groups |
| `H501 Do not use self.__dict__` | H501 | Explicit dict |
| `H701 DEPRECATED oslo.i18n` | H701 | `from myservice.i18n import _` |

---

## Running the Checks

```bash
tox -e pep8                                    # Full check (same as CI)
flake8 --select=H myservice/                   # Hacking only
flake8 --select=H myservice/api/v1/resources.py  # Single file
grep -r "H[0-9]\{3\}" tox.ini setup.cfg       # Show configured rules
```

---

## See Also

- `oslo-patterns.md` — Oslo library usage that hacking compliance depends on
- `rpc-versioning.md` — Version rules for API methods
