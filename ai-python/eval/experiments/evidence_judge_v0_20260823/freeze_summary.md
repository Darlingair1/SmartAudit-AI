# Evidence Judge Benchmark V1 Freeze

## Frozen dataset

- Dataset: `eval/judge/claim_evidence_benchmark_v1.jsonl`
- SHA256: `e8c68404be3ef8535c8f3cc3f9fe54418616870ad993bf2d676f2eee4cf189f7`
- Cases: 120 reviewed, 0 draft
- Labels: SUPPORTED/PARTIAL/UNSUPPORTED = 40/40/40
- Source audited dataset SHA256: `b2773be96915f917ff9ff0155c2f6fea270fe3fedacbc238937e3f982690bfde`
- Source commit: `cf29aae27f51d02ff194d42d156315ebd038be25`
- Annotation guideline: `claim_evidence_v1`
- Adjudication status: `complete`
- Unresolved label conflicts: 0

## Audit semantics

The previous ambiguous single `action` field is now represented as:

- `label_action`: KEEP for all 120 records; no automatic relabeling occurred.
- `text_action`: KEEP 72, REWRITE 48.

Audit coverage was 88/120 (all 80 PARTIAL/UNSUPPORTED plus 8 deterministic SUPPORTED samples). The 48 rewrites changed claim wording only. No gold label was changed or selected using Judge predictions. The adjudication pass checked exact/equivalent evidence conflicts and found no unresolved conflict in the frozen records.

## Fresh v0 comparison

Both original and frozen datasets were evaluated from scratch using the unchanged `services/evidence_judge.py`; no predictions were reused. All reported metrics were identical:

| Metric | Original | Audited/Frozen | Delta |
|---|---:|---:|---:|
| Accuracy | 0.425000 | 0.425000 | 0 |
| Macro-F1 | 0.336594 | 0.336594 | 0 |
| SUPPORTED Precision | 0.366972 | 0.366972 | 0 |
| SUPPORTED Recall | 1.000000 | 1.000000 | 0 |
| PARTIAL F1 | 0.139535 | 0.139535 | 0 |
| UNSUPPORTED Recall | 0.200000 | 0.200000 | 0 |
| Abstention Precision / Recall | 1.000000 / 0.075000 | 1.000000 / 0.075000 | 0 / 0 |
| Human review rate | 0.091667 | 0.091667 | 0 |
| Unsafe acceptance rate | 0.862500 | 0.862500 | 0 |

Prediction transitions caused by rewrites: 0. The unchanged result is expected because rewrites preserve the main lexical claim and the Judge implementation is unchanged.

Validator status: `valid`. Full test suite remains the required final gate; no Judge v1 was implemented.
