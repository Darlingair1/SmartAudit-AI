"""Compare retrieval reports without changing retrieval behavior."""
from __future__ import annotations

import argparse
import hashlib
import json
import hashlib
from pathlib import Path
from typing import Any


STAGES = ("lexical_candidates", "vector_candidates", "rrf_input", "rrf_scores", "final_candidate_ids")


def _ids(items: Any, key: str = "candidate_id") -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item.get(key) if isinstance(item, dict) else item) for item in items]


def compare_reports(left_path: Path, right_path: Path) -> dict[str, Any]:
    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    left_cases = {case["case_id"]: case for case in left.get("cases", [])}
    right_cases = {case["case_id"]: case for case in right.get("cases", [])}
    changed = []
    for case_id in sorted(set(left_cases) | set(right_cases)):
        a = left_cases.get(case_id, {})
        b = right_cases.get(case_id, {})
        a_final = _ids(a.get("top_results"), "chunk_id")
        b_final = _ids(b.get("top_results"), "chunk_id")
        if a_final == b_final:
            continue
        da = a.get("timing", {}).get("retrieval_stage_diagnostics", {})
        db = b.get("timing", {}).get("retrieval_stage_diagnostics", {})
        first = None
        for stage in STAGES:
            av = da.get(stage, [])
            bv = db.get(stage, [])
            if stage == "lexical_candidates" or stage == "vector_candidates":
                av, bv = _ids(av), _ids(bv)
            elif stage == "rrf_scores":
                av, bv = [(x.get("candidate_id"), x.get("score")) for x in av], [(x.get("candidate_id"), x.get("score")) for x in bv]
            if av != bv:
                first = stage
                break
        changed.append({"case_id": case_id, "first_divergence": first or "final_candidate_ids", "left_ids": a_final, "right_ids": b_final})
    def file_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def settings(result: dict[str, Any]) -> list[str]:
        return sorted({str(c.get("timing", {}).get("settings_fingerprint") or "") for c in result.get("cases", [])})

    return {
        "left": str(left_path),
        "right": str(right_path),
        "metadata": {
            key: {"left": left.get("metadata", {}).get(key), "right": right.get("metadata", {}).get(key)}
            for key in ("git_commit", "dataset", "embedding_model", "reranker_model", "settings_fingerprint", "environment", "document_fingerprints")
        },
        "dataset_hash": {"left": file_hash(Path(left["metadata"]["dataset"])), "right": file_hash(Path(right["metadata"]["dataset"]))},
        "settings_fingerprints": {"left": settings(left), "right": settings(right)},
        "metrics": {"left": left.get("metrics"), "right": right.get("metrics")},
        "ranking_fingerprint": {"left": left.get("metadata", {}).get("ranking_fingerprint"), "right": right.get("metadata", {}).get("ranking_fingerprint")},
        "changed_case_count": len(changed),
        "changed_cases": changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare_reports(args.left, args.right)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
