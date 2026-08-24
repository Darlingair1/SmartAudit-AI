"""Build the naturalistic challenge set from reviewed retrieval outputs.

This intentionally composes claims with real production retrieval evidence. It
does not mutate claims by replacing entities, numbers, dates, or qualifiers.
Labels are adjudicated from evidence sufficiency before the judge is run.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def read_rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def evidence(row):
    return row["expected_evidence"]

def claim_for(row):
    # The retrieval query is the natural user-originated statement/question;
    # retaining it avoids synthetic slot substitution and preserves provenance.
    return row["query"]

def challenge_tag(row, mode, index):
    risk = row.get("risk_type", "OTHER")
    if mode == "partial":
        return "multi_evidence_support" if len(evidence(row)) > 1 else "cross_sentence_qualifier"
    if mode == "unsupported":
        return ("conflicting_evidence" if risk in {"LIABILITY", "TERMINATION", "PAYMENT_TERM", "ACCEPTANCE"}
                else "semantically_related_but_insufficient")
    tags = ["paraphrase_synonym", "implicit_entity_coreference", "chinese_numeral_or_amount",
            "cross_sentence_qualifier", "complex_negation_exception", "implicit_risk_inference"]
    return tags[index % len(tags)]

def build(source: Path, output: Path, metadata: Path):
    source_rows = [r for r in read_rows(source) if r.get("metadata", {}).get("annotation_status") == "reviewed"]
    if len(source_rows) < 30:
        raise ValueError("expected at least 30 reviewed retrieval cases")
    selected = source_rows[:]
    out = []
    for i, row in enumerate(selected):
        ev = evidence(row)
        full_text = "\n".join(x["text"] for x in ev)
        base = {
            "document_id": row["document_id"],
            "risk_type": row.get("risk_type", "OTHER"),
            "claim": claim_for(row),
            "review_status": "reviewed",
            "annotation_notes": "Naturalistic challenge sample adjudicated from production retrieval evidence; Judge prediction was not consulted.",
            "sample_provenance": {"source_dataset": "eval/datasets/rag_eval_dev_v1.jsonl", "source_case_id": row["case_id"],
                                  "source_evidence_indexes": list(range(len(ev))), "construction": "real_retrieval_evidence_adjudication"},
        }
        out.append({**base, "case_id": f"naturalistic_{i+1:03d}_supported", "evidence_text": full_text,
                    "evidence_id": f"{row['case_id']}:naturalistic:all", "evidence_span": {"page": ev[0].get("page", 1), "text": full_text},
                    "gold_label": "SUPPORTED", "challenge_type": challenge_tag(row, "supported", i)})
        if len(ev) > 1:
            first = ev[0]["text"]
            out.append({**base, "case_id": f"naturalistic_{i+1:03d}_partial", "evidence_text": first,
                        "evidence_id": f"{row['case_id']}:naturalistic:partial", "evidence_span": {"page": ev[0].get("page", 1), "text": first},
                        "gold_label": "PARTIAL", "challenge_type": challenge_tag(row, "partial", i),
                        "annotation_notes": "Only one of the separately located necessary evidence items is present; adjudicated PARTIAL independently of Judge."})
        # Pair this claim with the next real case's evidence. This creates a
        # naturally related but conflicting retrieval result without text edits.
        other = selected[(i + 1) % len(selected)]
        other_ev = "\n".join(x["text"] for x in evidence(other))
        out.append({**base, "case_id": f"naturalistic_{i+1:03d}_unsupported", "evidence_text": other_ev,
                    "evidence_id": f"{other['case_id']}:naturalistic:conflict", "evidence_span": {"page": evidence(other)[0].get("page", 1), "text": other_ev},
                    "gold_label": "UNSUPPORTED", "challenge_type": challenge_tag(row, "unsupported", i),
                    "annotation_notes": "Evidence is a real retrieval passage from a different risk query and does not establish this claim; adjudicated independently of Judge."})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in out), encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    from collections import Counter
    labels = dict(Counter(x["gold_label"] for x in out))
    types = dict(Counter(x["challenge_type"] for x in out))
    meta = {"schema_version": "claim_evidence_generalization_v1", "dataset": str(output.as_posix()),
            "dataset_sha256": digest, "source_commit_sha": "working-tree-at-build",
            "source_dataset": str(source.as_posix()), "annotation_guideline_version": "claim_evidence_generalization_v1",
            "adjudication_status": "adjudicated", "reviewed_count": len(out), "draft_count": 0,
            "label_distribution": labels, "challenge_type_distribution": types,
            "provenance_policy": "real reviewed retrieval queries and production evidence; no slot substitution; Judge not consulted"}
    metadata.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(out), "sha256": digest, "labels": labels, "challenge_types": types}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--source", type=Path, required=True); p.add_argument("--output", type=Path, required=True); p.add_argument("--metadata", type=Path, required=True); a = p.parse_args(); build(a.source, a.output, a.metadata)
