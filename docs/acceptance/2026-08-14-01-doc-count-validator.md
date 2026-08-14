# Acceptance: README doc-count validator

- Date: 2026-08-14
- Peer: `e3c5b3b8-505a-41de-a2c0-bd56c815a2f0` (`Implement README count validation`)
- Brief/branch: make `scripts/validate-doc-counts.py` gate the README Four Layers table, add success and mismatch coverage, and keep the final tree internally consistent; `peer/doc-count-validator`
- Candidate commits: `4ad8ad9940ee68fe28b048f4a26b1d3c93938771`, `2d32a9cd131850195b23f7762dda6e08435ac52e`

## Evidence

- `python3 scripts/validate-doc-counts.py` -> exit 0; tail: `All count claims agree with filesystem.`
- `uvx --isolated --from pytest pytest -q scripts/tests/test_validate_doc_counts.py` -> exit 0; tail: `3 passed in 0.18s`
- `uvx --isolated --from pytest pytest -q scripts/tests/test_validate_doc_counts.py::test_four_layers_mismatch_is_actionable_and_fails` -> exit 0; tail: `1 passed in 0.10s`; the test asserts the validator itself exits 1 and prints the exact filesystem-versus-README values.
- `uvx --isolated --from ruff==0.15.12 ruff check . --config pyproject.toml` -> exit 0; tail: `All checks passed!`
- `uvx --isolated --from ruff==0.15.12 ruff format --check . --config pyproject.toml` -> exit 0; tail: `594 files already formatted`
- `uvx --isolated --from pytest --with-requirements requirements.lock --with pillow --with numpy --with pip pytest --tb=short -q` -> exit 0; tail: `7600 passed, 25 skipped, 146 xfailed, 7 warnings in 375.53s`
- `git diff --check fix/verify-doc-counts...HEAD` -> exit 0; no output.
- `git status --short --branch` -> exit 0; tail: `## peer/doc-count-validator`.

## Verdict

Accepted after corrective round 1.

The initial candidate correctly implemented comparison and failure output but left the clean repository gate red because the Four Layers table itself was stale. The corrective round changed only the stale count cells, after which targeted, lint, formatting, validator, and full-suite gates passed.

## Defects Found And Fixed

- The pre-change validator reported filesystem truth without parsing or enforcing the Four Layers table.
- The table had three stale values while the README intro already held the current filesystem values.
- The first candidate preserved the stale table because the Lead brief incorrectly excluded all README edits; the corrected brief authorized only those table cells.

## Premises Disproved

- "README must remain unchanged" was false for the final deliverable. Preserving intended README semantics required aligning its stale table with the already-correct intro and filesystem truth.

## Cost Of Recurrence

Measured: a recurrence would again permit stale public figures to survive the named CI validator and would require another table audit, deliberate-failure proof, and corrective review round. This occurrence involved three stale cells and one corrective round.

Structural signal: suspected

Lens: mechanism-free claim

Bounded checkpoint: Checked whether the named validator converted the Four Layers documentation claim into a failing comparison rather than only printing filesystem truth.

Causal mechanism: A validator that never parses the claimed table can remain green while the public figures drift.

Observed cost: Measured - three stale table cells and one corrective round before the clean gate passed.

Strongest counterargument: The generic prose-count scanner already covered many documentation claims, and the table's label-before-number shape simply fell outside that established grammar.

Structural verdict: confirmed

Memory: experience-candidate

## Archive Authorization

Authorized after the accepted commits merge cleanly into the Lead integration branch.
