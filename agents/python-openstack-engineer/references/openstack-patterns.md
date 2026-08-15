# OpenStack Patterns

## Oslo.config Integration

```python
from oslo_config import cfg

service_opts = [
    cfg.StrOpt('api_url', default='http://localhost:8080', help='API endpoint URL'),
    cfg.IntOpt('workers', default=4, min=1, help='Number of worker processes'),
]

CONF = cfg.CONF
CONF.register_opts(service_opts, group='myservice')
```

## Oslo.messaging RPC

```python
from oslo_messaging import rpc

class MyServiceAPI(object):
    RPC_API_VERSION = '1.0'

    def __init__(self):
        target = messaging.Target(topic='myservice', version=self.RPC_API_VERSION)
        self.client = rpc.get_client(target)

    def call_method(self, ctxt, arg1):
        cctxt = self.client.prepare(version='1.0')
        return cctxt.call(ctxt, 'method_name', arg1=arg1)
```

## Database Migration

```python
# alembic/versions/001_initial_schema.py
def upgrade():
    op.create_table(
        'resources',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )

def downgrade():
    op.drop_table('resources')
```

See `oslo-patterns.md` for comprehensive Oslo library usage.
