"""Calibrate trusted frozen buggy fixtures and authored reference solutions only.

Runs offline and does not modify the corpus. Keep this script and its output out
of model context. Never pass generated code to these in-process checkers.
This is not a generated execution evaluation. Use --output to save a record.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

CORPUS = Path(__file__).resolve().parent


def calibrate():
    results = []
    for directory in sorted((CORPUS / "fixtures").iterdir()):
        if not directory.is_dir():
            continue
        name = directory.name
        checker = CORPUS / "evaluators" / name / "check.py"
        row = {"fixture": name}
        for source in ["fixtures", "reference_solutions"]:
            result = subprocess.run(
                [sys.executable, "-B", str(checker), str(CORPUS / source / name)],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            row[source] = {"exit": result.returncode, "result": json.loads(result.stdout)}
        if row["fixtures"]["exit"] == 0:
            raise RuntimeError(f"{name}: buggy original unexpectedly passes")
        if row["reference_solutions"]["exit"] != 0:
            raise RuntimeError(f"{name}: reference solution fails")
        results.append(row)
    if len(results) != 6:
        raise RuntimeError(f"Expected six fixtures, found {len(results)}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional calibration record path")
    args = parser.parse_args()
    results = calibrate()
    if args.output:
        args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"calibrated": len(results), "results": results}))


if __name__ == "__main__":
    main()
