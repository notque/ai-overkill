"""Trusted-fixture calibration only. Usage: grade_execution.py FIXTURE_NAME TRUSTED_WORKSPACE.

Only run against the checked-in buggy fixtures and authored reference solutions.
This imports Python in the checker process; it is not an isolated evaluator and
must never evaluate generated or otherwise untrusted code. Calibration results
establish known-original/reference behavior, not generated execution quality.
"""

import ast
import importlib.util
import json
import sys
from pathlib import Path

name, location = sys.argv[1:]
p = Path(location)
checks = []


def check(label, fn):
    try:
        passed = bool(fn())
        checks.append({"criterion": label, "pass": passed})
    except Exception as exc:
        checks.append({"criterion": label, "pass": False, "error": type(exc).__name__})


def module(file):
    spec = importlib.util.spec_from_file_location("submission", p / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if name == "duplicate_email":
    m = module("app.py")

    def creates():
        rows = []
        a = m.create_user(rows, "a@example.test")
        b = m.create_user(rows, "b@example.test")
        return (
            rows == [{"id": 1, "email": "a@example.test"}, {"id": 2, "email": "b@example.test"}]
            and a == rows[0]
            and b == rows[1]
        )

    def rejects():
        rows = [{"id": 1, "email": "a@example.test"}]
        try:
            m.create_user(rows, "a@example.test")
        except ValueError:
            return rows == [{"id": 1, "email": "a@example.test"}]
        return False

    check("distinct users preserve creation result", creates)
    check("duplicate rejects without mutation", rejects)
    check("list_users behavior unchanged", lambda: m.list_users([{"id": 1}]) == [{"id": 1}])

    def unrelated_unchanged():
        original = Path(__file__).parent / "fixtures" / "duplicate_email" / "app.py"

        def other_defs(path):
            return [
                ast.dump(n, include_attributes=False)
                for n in ast.parse(path.read_text()).body
                if not (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "create_user")
            ]

        return other_defs(original) == other_defs(p / "app.py")

    check("other endpoint source unchanged", unrelated_unchanged)
elif name == "health_status":
    m = module("health.py")
    check("valid success boundaries", lambda: all(m.is_healthy(x) is True for x in [200, 204, 299]))
    check(
        "HTTP errors and redirects rejected",
        lambda: all(m.is_healthy(x) is False for x in [100, 199, 300, 301, 404, 503]),
    )
    check("absent response fails", lambda: m.is_healthy(None) is False)
elif name == "cart_quantity":
    m = module("cart.py")
    check(
        "quantity counted across lines",
        lambda: m.cart_total([{"unit_price": 12, "quantity": 2}, {"unit_price": 5, "quantity": 3}]) == 39,
    )
    check("empty cart stays zero", lambda: m.cart_total([]) == 0)
    check("zero quantity contributes zero", lambda: m.cart_total([{"unit_price": 99, "quantity": 0}]) == 0)
elif name == "label_only":

    def load():
        return json.loads((p / "ui.json").read_text())

    check("visible label corrected", lambda: load()["button_label"] == "Submit")
    check("external telemetry identifier preserved", lambda: load()["telemetry_key"] == "Sumbit")
    check(
        "no additional configuration changes", lambda: load() == {"button_label": "Submit", "telemetry_key": "Sumbit"}
    )
    check(
        "no unrelated files", lambda: all(f.name == "ui.json" or ".git" in f.parts for f in p.rglob("*") if f.is_file())
    )
elif name == "numeric_sort":
    m = module("prices.py")
    rows = [
        {"id": "a", "price": "100"},
        {"id": "b", "price": "9"},
        {"id": "c", "price": "9.0"},
        {"id": "d", "price": "-2.5"},
    ]
    check(
        "numeric ordering including decimal and negative",
        lambda: [r["id"] for r in m.sort_prices(rows)] == ["d", "b", "c", "a"],
    )
    check(
        "records preserved",
        lambda: sorted(m.sort_prices(rows), key=lambda r: r["id"]) == sorted(rows, key=lambda r: r["id"]),
    )
    check(
        "does not mutate input and empty works",
        lambda: m.sort_prices(rows) is not rows and rows[0]["id"] == "a" and m.sort_prices([]) == [],
    )
elif name == "sample_timeout":
    check(
        "example timeout changed",
        lambda: json.loads((p / "config.example.json").read_text()) == {"timeout_seconds": 10},
    )
    check("production bytes preserved", lambda: (p / "production.json").read_bytes() == b'{"timeout_seconds":5}\n')
    check(
        "no unrelated files",
        lambda: all(
            f.name in {"config.example.json", "production.json"} or ".git" in f.parts
            for f in p.rglob("*")
            if f.is_file()
        ),
    )
else:
    raise SystemExit("unknown fixture")
print(json.dumps({"fixture": name, "checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks)}))

raise SystemExit(0 if all(c["pass"] for c in checks) else 1)
