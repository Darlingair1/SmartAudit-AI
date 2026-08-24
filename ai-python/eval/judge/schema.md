# Claim-Evidence Benchmark Schema v1

Each JSONL record contains `case_id`, `document_id`, `risk_type`, `claim`,
`evidence_text`, `evidence_id`, `evidence_span`, `gold_label`, `review_status`,
and `annotation_notes`. Labels are exactly `SUPPORTED`, `PARTIAL`, or
`UNSUPPORTED`; review status is `draft` or `reviewed`.

`SUPPORTED` means the evidence directly supports the core fact and necessary
qualifiers. `PARTIAL` means a material qualifier in the claim is not supported.
`UNSUPPORTED` means the evidence is irrelevant, conflicting, or does not
support a material fact in the claim.

Dataset-level provenance and hashes are stored in the adjacent metadata JSON.
