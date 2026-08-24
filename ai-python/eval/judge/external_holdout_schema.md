# Claim-Evidence External Holdout Schema v1

Each JSONL record contains `case_id`, `document_id`, `risk_type`, `claim`,
`evidence`, `gold_label`, `review_status`, `annotation_notes`, `challenge_tags`,
`source_pipeline_provenance`, `initial_label`, `adjudicated_label`,
`adjudication_notes`, and `label_confidence`.

`evidence` is a non-empty array. Each item contains `evidence_id`, `text`, and
available page/chunk metadata. Evidence items are actual retrieval outputs; the
schema does not require a single span.

Labels are `SUPPORTED`, `PARTIAL`, or `UNSUPPORTED`. Every frozen record must
be `reviewed`, adjudicated, and free of unresolved annotation conflicts.
Challenge tags describe naturally observed properties and must never document
controlled perturbation or benchmark-generated negative construction.

Dataset metadata records document provenance and hashes, dataset SHA256,
creation timestamp, pipeline code provenance, annotation guideline version,
natural distributions, adjudication status, and pipeline-realism counts.
