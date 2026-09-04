"""Verify and replay archived evidence locally without making model calls."""

import hashlib
import json
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    """Preserve archived bytes; translate historical paths only during file access."""
    with tempfile.TemporaryDirectory(prefix="base-writing-replay-") as directory:
        unpacked = Path(directory)
        with tarfile.open(HERE / "evidence.tar.gz") as archive:
            archive.extractall(unpacked, filter="data")
        entries = (HERE / "ARTIFACT-SHA256SUMS").read_text().splitlines()
        for entry in entries:
            expected, name = entry.split("  ", 1)
            actual = hashlib.sha256((unpacked / name).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"Archive digest mismatch: {name}")
        trial = unpacked / "vexjoy-base-rules-trial"
        expected_report = json.loads((trial / "RECOVERY-REPORT.json").read_text())
        sys.path.insert(0, str(trial / "harness"))
        # Imports execute only the frozen offline parser and assessor definitions.
        __import__("runner")
        __import__("judge")
        __import__("assess")
        source = (trial / "recovery_report.py").read_text()
        original_open = Path.open
        original_stat = Path.stat

        def translated(path):
            for name in ("vexjoy-base-rules-trial", "vexjoy-base-rules-corpus"):
                prefix = Path("/tmp") / name
                if path.is_relative_to(prefix):
                    return unpacked / name / path.relative_to(prefix)
            return path

        def archived_open(path, *args, **kwargs):
            return original_open(translated(path), *args, **kwargs)

        def archived_stat(path, *args, **kwargs):
            return original_stat(translated(path), *args, **kwargs)

        namespace = {
            "__name__": "archived_report",
            "__file__": "/tmp/vexjoy-base-rules-trial/recovery_report.py",
        }
        Path.open = archived_open
        Path.stat = archived_stat
        try:
            exec(compile(source, namespace["__file__"], "exec"), namespace)
            result = namespace["report"]()
        finally:
            Path.open = original_open
            Path.stat = original_stat
        if result != expected_report:
            raise ValueError("Recomputed report differs from archived final report")
        print(f"Verified {len(entries)} artifacts; exact report replay: {result['verdict']}")
        print(json.dumps(result["experiment_cost"], indent=2))


if __name__ == "__main__":
    main()
