# Retrieval Evaluation Dataset Schema v1

Each non-empty JSONL line is one case. The required fields are:

- `case_id`: unique, non-empty case identifier.
- `document_id`: stable identifier used to locate and isolate the document.
- `query`: retrieval query.
- `expected_evidence`: array of `{ "page": positive integer, "text": non-empty string }` objects. It may be empty for a no-risk case.
- `metadata.source_type`: one of `synthetic`, `public`, `manually_annotated`, or `anonymized`.

The following v1 fields are optional: `risk_type`, `expected_answer`,
`expected_reason_codes`, `metadata.contract_type`, `metadata.difficulty`,
`metadata.document_path`, `metadata.purpose`, `metadata.annotation_status`,
and `metadata.error_review_category`. A relative `document_path` is resolved
from the dataset directory. `annotation_status` is `draft` or `reviewed`; the
runner excludes explicit drafts by default. Unknown fields are retained to
permit compatible annotation extensions such as evidence roles, clause IDs,
conflicts, and cross-page links.

Example:

```json
{
  "case_id": "contract_001_q_001",
  "document_id": "contract_001",
  "query": "Is liability materially imbalanced?",
  "risk_type": "LIABILITY_IMBALANCE",
  "expected_answer": "risk",
  "expected_evidence": [{"page": 12, "text": "The supplier shall..."}],
  "expected_reason_codes": [],
  "metadata": {
    "contract_type": "purchase",
    "difficulty": "medium",
    "source_type": "manually_annotated",
    "document_path": "documents/contract_001.pdf"
  }
}
```
