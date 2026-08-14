# Acceptance: saved ablation run query

- Brief: Add a small repository-appropriate query surface for runs written by `scripts/skill-eval-ablation.py`, with meaningful automated coverage and project quality gates. Excluded storage redesign, hook behavior changes, and unrelated cleanup.
- Peer / branch: `73137d1b-67b8-4789-b7d8-608418badd3e` / `peer/saved-run-query`
- Accepted commit: `70dade07038205b3c77a64d9e44e59616df4a26e`

## Evidence

- `uv run --no-project --with pytest --with pyyaml --with ruff python -m pytest scripts/tests/test_skill_eval_ablation.py hooks/tests/test_telemetry_envelope.py -q` — exit 0; tail: `37 passed in 2.31s`.
- `uvx ruff check scripts/learning-db.py scripts/tests/test_skill_eval_ablation.py --config pyproject.toml` — exit 0; tail: `All checks passed!`.
- `uvx ruff format --check scripts/learning-db.py scripts/tests/test_skill_eval_ablation.py --config pyproject.toml` — exit 0; tail: `2 files already formatted`.
- `uvx ruff check . --config pyproject.toml` — exit 0; tail: `All checks passed!`.
- `git diff --check 586f89bc..70dade07038205b3c77a64d9e44e59616df4a26e` — exit 0; no output.
- `git status --short --branch` in the Peer worktree — exit 0; tail: `## peer/saved-run-query`.
- Peer broad gate: `uv run --with ruff ruff format --check . --config pyproject.toml` — exit 1; 62 unrelated pre-existing files were reported unformatted.
- Peer broad gate: `uv run --with pytest --with pyyaml --with pillow --with numpy python -m pytest --tb=short -q` — exit 1; tail: `7499 passed, 22 failed, 28 skipped, 146 xfailed`; reported failures were outside changed files and tied to missing `jsonschema`, system `pip`, or generated-index isolation.

## Verdict

- Acceptance verdict: accepted; corrective rounds: 0.
- Defects found and fixed: the Peer corrected one Ruff formatting issue in the new query code before commit. Lead review found no remaining scope defect.
- Premises disproved: repository-wide format and pytest commands are not currently fully green in this environment, despite focused and adjacent gates passing.
- Cost of recurrence: each small Python change would repeat a full-suite run and triage 62 formatter findings plus 22 unrelated test failures before establishing changed-scope health.
- Archive authorization: authorized after merge; accepted verdict.

Structural signal: suspected
Lens: avoidable taxes
Bounded checkpoint: repository-wide Ruff format and pytest evidence for this bounded Python change.
Causal mechanism: broad gates include existing format debt and environment-sensitive tests outside the changed scope.
Observed cost: measured one 62-file format failure and one dependency-complete run ending with 22 failures after 7,499 passes.
Strongest counterargument: the repository defines tool configuration but no Make target declaring these exact broad commands as mandatory gates.
Structural verdict: confirmed
Memory: local-defect
