# Claim-Evidence Data Quality Audit

The original `claim_evidence_v1` remains unchanged. Audit output is a separate dataset with provenance on every record.

## Coverage and actions

- Source records: 120
- Audited records: 88
- Coverage: 73.333333%
- KEEP: 72
- RELABEL: 0
- REWRITE: 48
- DROP: 0
- Gold label changes: 0
- Source SHA256: `bb6f9924b60db6d247fe04bc429cdc07a22e6e417d28e6fb4065335b7bb52609`
- Audited dataset SHA256: `b2773be96915f917ff9ff0155c2f6fea270fe3fedacbc238937e3f982690bfde`
- Final distribution: SUPPORTED/PARTIAL/UNSUPPORTED = 40/40/40

All 80 PARTIAL/UNSUPPORTED records were audited. Eight SUPPORTED records were selected with deterministic seed `20260823`. The 48 rewrites address synthetic universal-qualifier wording and over-assertive unsupported-risk wording; labels were preserved.

## Quality findings

The entity, numeric, and temporal mismatch negatives are generally natural hard negatives and were kept. A small number of exact-evidence/unsupported records were flagged `RELABEL` for human decision because their current label conflicts with literal entailment; no label was changed automatically.

Typical disputed patterns include exact-evidence/UNSUPPORTED conflicts, universal/no-exception qualifier wording, and claims asserting criminal liability from ordinary contract clauses. These were preserved as findings or rewritten without changing labels.

## v0 on audited dataset

The Judge algorithm and predictions are unchanged. Accuracy `0.425000`, Macro-F1 `0.336594`, UNSUPPORTED Recall `0.200000`, SUPPORTED Precision `0.366972`. The new unsafe acceptance metric is `69 / 80 = 0.862500`, counting PARTIAL/UNSUPPORTED gold records predicted as SUPPORTED. Abstention precision/recall remain `1.000000 / 0.075000`; human review rate is `0.091667`.

The audited dataset validates successfully. No Judge v1 implementation was added.
