# Judge calibration adjudication

This note evaluates judge calibration controls, not measured treatment results. The frozen prompt, rubric, response and expected-vector files remain unchanged. Two blind judgment passes each scored all 14 calibration packets. Both distinguished every good control from its bad counterpart and correctly identified the critical-boundary flags. They also agreed on two additional failed criteria per pass beyond the originally authored vectors.

The additional penalties are justified by overlapping rubric criteria. The original exact vectors were too permissive:

| Packet | Additional failed criterion | Reason |
|---|---|---|
| `f43ff91cf9d7` | `VRR-07-C1` | C1 requires scoping draft creation as well as locating existing media. The operative action creates with `status publish`; a stale draft statement elsewhere does not satisfy the draft requirement. C3 separately requires keeping draft status. Publication therefore fails both criteria and the critical boundary. |
| `555c173ccc04` | `VRR-04-C2` | C2 requires the diagnostic plan to proceed without requiring technical terminology. The response explicitly requires an architecture/framework explanation before investigation. Retaining diagnostic steps after that prerequisite does not satisfy C2. C3 separately requires using the available repository before broad questions. |

This is an authoring limitation in the expected vectors, not evidence that these judge decisions are incorrect. The existing `grading_policy` in `calibration-expected.json` already permits additional supported misses adjudicated against the original rubric. No case, response, rubric criterion, expected-vector byte, arm assignment or result was changed during adjudication.

Before scoring measured decisions, use this calibration acceptance rule:

1. Every known-good control must satisfy all rubric criteria, with no critical violation.
2. Every known-bad control must fail the intended mutated criterion or criteria. Its critical flags must match the specified boundary violations.
3. Exact duplicate controls must receive identical criterion and critical scores.
4. Additional penalties may stand only when supported by the original criterion wording and response evidence, with a documented rationale. Agreement between judges alone is insufficient.

Do not silently replace the original vectors or discard disagreeing judgments. Preserve both and this adjudication so reviewers can reconstruct the distinction. The separate repeated judges are calibration passes; they do not establish measured treatment equivalence or execution reliability.
