# Flask + Jinja2 Web Application Reference

> **Scope**: Flask app structure (blueprints, app factory), Jinja2 template behavior in production, CSRF configuration, gunicorn/systemd/nginx serving stack, session cookies, static-file serving. Generic Python security lives elsewhere; Peewee/SQLite data access belongs to sqlite-peewee-engineer.
> **Version range**: Flask 2.x/3.x, Jinja2 3.x, gunicorn 20+
> **Source incidents**: /home/feedgen/mmr-ratings production history (2025-2026)

## Production Serving Model

A Flask app in production is three layers; a bug can live in any of them.

| Layer | Owns | Restart/refresh trigger |
|---|---|---|
| gunicorn workers (systemd unit) | Python code AND Jinja templates (cached per worker) | `systemctl restart <service>` — code edits are inert until restart |
| nginx | Public 80/443, static files via `alias`/`root`, reverse proxy to loopback | `nginx -t && systemctl reload nginx` for config; nothing for file content |
| Flask dev server | Auto-reload, debugger | Development only, loopback only |

**The classic miss**: "changes not taking effect" after editing templates or Python. Gunicorn workers cache imported modules and compiled Jinja templates for the worker's lifetime. Fix: restart the service. Dev mode auto-reloads; production reloads only on service restart.

Bind app servers to `127.0.0.1` and let nginx own the public ports. Pattern: `gunicorn -w 4 -b 127.0.0.1:8001 "server.app:app"` behind an nginx `proxy_pass`.

## Blueprints and App Factory

```python
# Register blueprints once, at app creation. Verify registration in a smoke test:
def test_critical_routes_registered(self):
    rules = {r.rule for r in app.url_map.iter_rules()}
    self.assertIn('/api/rankings', rules)
```

- Blueprint route changes require service restart (see above).
- A blueprint imported but omitted from `app.register_blueprint()` fails silently: routes 404, no error at startup. The route-registration smoke test is the deterministic guard.
- Keep `url_prefix` on the registration call, in one place, rather than duplicated in every route decorator.

## CSRF: Global Protection, Explicit Exemptions

With Flask-WTF `CSRFProtect(app)`, every POST without a token returns 400. JSON APIs consumed by fetch() need explicit exemption per blueprint:

```python
csrf = CSRFProtect(app)
csrf.exempt(mmr_blueprint)   # JSON API, token-less fetch() clients
```

- Exempt at blueprint granularity; keep global protection enabled.
- Pin each exemption with a test (`test_mmr_blueprint_csrf_exempt`) so a refactor that drops the exemption fails CI instead of breaking clients with silent 400s.

## Jinja2 Production Behavior

| Behavior | Consequence | Handling |
|---|---|---|
| Templates compiled once per worker | Edited .html serves stale until restart | Restart service after template deploys |
| Autoescaping on for .html | Raw HTML needs explicit `\| safe` | Apply `\| safe` to server-generated markup only; user input stays escaped |
| `url_for('static', filename=...)` | Cache-busting needs a version query param | Add `?v=<sha>` or hashed filenames for player-facing assets |
| Missing variable renders as empty (default Undefined) | Typos ship as blank UI, no error | `app.jinja_env.undefined = StrictUndefined` in dev/staging |

## Static Files Through nginx

When nginx serves statics directly (`alias /srv/app/current/static/;`), file permissions are the contract:

- New files written mode 600 return **403** from nginx while the Flask dev server happily serves them. Symptom: unstyled page or dead JS in production only.
- Fix and prevention: `chmod 644` on every new static file; verify with `curl -sI https://<domain>/static/css/<file>.css` expecting 200.
- Deployed-tree statics are a **copy** (or release dir), separate from the working tree. Editing the repo's `static/` changes nothing until the deploy step syncs it.

## Sessions and Cookies

```python
app.config.update(
    SESSION_COOKIE_SECURE=True,    # cookie only over HTTPS — login breaks on plain-HTTP staging
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
```

- `SESSION_COOKIE_SECURE=True` + an HTTP-only staging host = login flows untestable there. Either issue the staging TLS cert or document the limitation; weakening the flag stays off the table.
- `FLASK_SECRET_KEY` comes from the environment (systemd `EnvironmentFile=`); code holds zero key material. Throwaway local servers use a random key: `FLASK_SECRET_KEY=$(openssl rand -hex 32)`.
- Staging gets its own secret/env file, separate from production's.

## Error-Fix Mappings

| Symptom | Root cause | Fix |
|---|---|---|
| Template/code edits invisible in prod | Worker module/template cache | `systemctl restart <service>` |
| Static file 403 only via nginx | File mode 600 under nginx `alias` | `chmod 644`, verify with curl |
| POST returns 400 from JSON client | CSRF token required, blueprint lacks exemption | `csrf.exempt(blueprint)` + pin test |
| Routes 404 after refactor | Blueprint registration missing | Route-registration smoke test; register in factory |
| Login works locally, fails on staging | `SESSION_COOKIE_SECURE` over HTTP | Issue TLS cert for the staging host |
| Service refuses to start after deploy | Import/syntax error in worker boot | `journalctl -u <service> -n 50`, read the traceback |
| Blank values rendered in page | Jinja default Undefined swallows typos | StrictUndefined in dev/staging |

## Verification Commands

```bash
sudo systemctl status <service> --no-pager        # workers up?
curl -s http://127.0.0.1:<port>/health            # app answers on loopback?
sudo journalctl -u <service> -n 50                # boot tracebacks
curl -sI https://<domain>/static/js/<file>.js     # nginx serves statics, 200 not 403
sudo nginx -t                                     # before any nginx reload
```
