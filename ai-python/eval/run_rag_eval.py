from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from eval.rag_eval_types import EvalSample


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def evaluate(dataset_path: Path, predictions_path: Path) -> dict:
    samples = [EvalSample.model_validate(x) for x in _load_jsonl(dataset_path)]
    preds = _load_jsonl(predictions_path)
    pred_map = {str(x.get("task_id")): x for x in preds}

    primary_hits = []
    supporting_hits = []
    exception_hits = []
    strict_page = []
    tolerant_page = []
    excerpt_scores = []

    for s in samples:
        pred = pred_map.get(s.task_id, {})
        evs = pred.get("retrieved_evidences", []) or []
        pred_pages = [int(x.get("page_no", 0)) for x in evs if int(x.get("page_no", 0)) > 0]
        pred_excerpts = [str(x.get("excerpt", "")) for x in evs]

        def role_recall(role: str) -> float:
            targets = [g for g in s.gold_evidences if g.evidence_role == role]
            if not targets:
                return 1.0
            hit = 0
            for t in targets:
                if t.gold_page_no in pred_pages:
                    hit += 1
            return hit / max(1, len(targets))

        primary_hits.append(role_recall("PRIMARY"))
        supporting_hits.append(role_recall("SUPPORTING"))
        exception_hits.append(role_recall("EXCEPTION"))

        for g in s.gold_evidences:
            if not pred_pages:
                strict_page.append(0.0)
                tolerant_page.append(0.0)
                continue
            best = pred_pages[0]
            strict_page.append(1.0 if best == g.gold_page_no else 0.0)
            tolerant_page.append(1.0 if abs(best - g.gold_page_no) <= 1 else 0.0)
            # crude excerpt score
            ge = g.gold_excerpt.replace(" ", "")
            best_overlap = 0.0
            for p in pred_excerpts[:5]:
                pe = p.replace(" ", "")
                if not ge or not pe:
                    continue
                inter = len(set(ge) & set(pe))
                best_overlap = max(best_overlap, inter / max(1, len(set(ge))))
            excerpt_scores.append(best_overlap)

    return {
        "sample_count": len(samples),
        "primary_evidence_recall": round(mean(primary_hits), 4) if primary_hits else 0.0,
        "supporting_evidence_recall": round(mean(supporting_hits), 4) if supporting_hits else 0.0,
        "exception_clause_recall": round(mean(exception_hits), 4) if exception_hits else 0.0,
        "strict_accuracy": round(mean(strict_page), 4) if strict_page else 0.0,
        "tolerant_accuracy": round(mean(tolerant_page), 4) if tolerant_page else 0.0,
        "excerpt_match_score": round(mean(excerpt_scores), 4) if excerpt_scores else 0.0,
    }


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    dataset = base / "rag_eval_set.jsonl"
    preds = base / "predictions.jsonl"
    report = evaluate(dataset, preds)
    out_dir = base / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# RAG Eval Report", ""]
    for k, v in report.items():
        md.append(f"- {k}: {v}")
    (out_dir / "eval_report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

