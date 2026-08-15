# OpenStack Error Handling

## Bare Except Clause (H201)
**Cause**: `except:` without exception type
**Solution**: Catch specific exceptions:
```python
try:
    do_something()
except SpecificException as e:
    LOG.error('Failed: %s', e)
```

## Missing i18n Translation
**Cause**: User-facing string without _()
**Solution**:
```python
from myservice.i18n import _
raise Exception(_('Resource not found'))
```

## Import Order Violation (H301-H307)
**Cause**: Imports not following OpenStack conventions
**Solution**: stdlib, third-party, project:
```python
import os
import sys

import eventlet
from oslo_config import cfg

from myservice import utils
```
