import subprocess
import sys
from pathlib import Path

p = Path(__file__).resolve().parents[2]
r = subprocess.run([sys.executable, "-B", str(p / "grade_execution.py"), "duplicate_email", sys.argv[1]], text=True)
raise SystemExit(r.returncode)
