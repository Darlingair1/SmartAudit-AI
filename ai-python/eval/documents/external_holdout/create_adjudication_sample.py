"""Create a label-blind, deterministic External Holdout adjudication sample."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = ROOT / "ai-python/eval/experiments/external_holdout_20260824"
CAPTURE = EXPERIMENT / "pipeline_capture"
OUT = EXPERIMENT / "adjudication_sample_v1"
UNIVERSE = CAPTURE / "cases_raw.jsonl"
PROVENANCE = CAPTURE / "pipeline_provenance.json"
SOURCE_SET = ROOT / "ai-python/eval/documents/external_holdout/pipeline_source_set.json"

SEED = 20260824
ALGORITHM_VERSION = "stratified_largest_remainder_v1"
ALLOCATION = {
    "1746527472741_5024.pdf": 40,
    "8a69c65e95a7fec40195faa1360d1770.pdf": 25,
    "8a69c8e290831b250190964f57453e46.pdf": 55,
}
ALGORITHM_SPEC = {
    "version": ALGORITHM_VERSION,
    "stratum": "document_filename + claim.riskType",
    "quota": "floor(target * stratum_size / document_size), then largest remainder",
    "quota_tie_break": "SHA256(seed + document_filename + risk_type)",
    "within_stratum": "Python random.Random seeded from SHA256(seed + document_filename + risk_type)",
    "output_order": "original capture_universe order",
    "prohibited_inputs": ["gold label", "evidence quality", "difficulty", "ranking", "reranker status", "Judge output"],
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def risk_type(row: dict[str, Any]) -> str:
    return str((row.get("claim") or {}).get("riskType") or "UNKNOWN").strip() or "UNKNOWN"


def deterministic_rank(*parts: object) -> str:
    return sha256_bytes(":".join(str(part) for part in parts).encode("utf-8"))


def allocate_quotas(rows: list[dict[str, Any]], target: int, filename: str) -> dict[str, int]:
    counts = Counter(risk_type(row) for row in rows)
    if target >= len(rows):
        return dict(counts)
    quotas = {key: (target * count) // len(rows) for key, count in counts.items()}
    assigned = sum(quotas.values())
    candidates = sorted(
        counts,
        key=lambda key: (
            -((target * counts[key]) % len(rows)),
            deterministic_rank(SEED, filename, key, "quota"),
        ),
    )
    for key in candidates:
        if assigned >= target:
            break
        if quotas[key] < counts[key]:
            quotas[key] += 1
            assigned += 1
    if assigned != target:
        raise RuntimeError(f"quota allocation failed for {filename}: {assigned} != {target}")
    return quotas


def select_document(rows: list[dict[str, Any]], target: int, filename: str) -> tuple[set[str], dict[str, int]]:
    quotas = allocate_quotas(rows, target, filename)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[risk_type(row)].append(row)
    selected: set[str] = set()
    for key in sorted(groups):
        group = list(groups[key])
        seed_value = int(deterministic_rank(SEED, filename, key, "within")[:16], 16)
        random.Random(seed_value).shuffle(group)
        selected.update(row["case_id"] for row in group[: quotas[key]])
    return selected, quotas


def main() -> None:
    universe_bytes = UNIVERSE.read_bytes()
    original_lines = [line for line in universe_bytes.splitlines(keepends=True) if line.strip()]
    rows = [json.loads(line) for line in original_lines]
    if len(rows) != 289:
        raise RuntimeError(f"capture universe must contain 289 cases, got {len(rows)}")
    if any(any(key in row for key in ("gold_label", "adjudicated_label", "predicted_label")) for row in rows):
        raise RuntimeError("capture universe unexpectedly contains labels or predictions")

    OUT.mkdir(parents=True, exist_ok=True)
    algorithm_fingerprint = canonical_hash(ALGORITHM_SPEC)
    planned_manifest = {
        "schema_version": "external_holdout_sampling_manifest_v1",
        "status": "PLANNED_BEFORE_ANNOTATION",
        "sampling_seed": SEED,
        "sampling_algorithm_version": ALGORITHM_VERSION,
        "sampling_algorithm": ALGORITHM_SPEC,
        "sampling_algorithm_fingerprint": algorithm_fingerprint,
        "allocation": ALLOCATION,
        "source_universe_path": str(UNIVERSE.relative_to(ROOT)).replace("\\", "/"),
        "source_universe_count": len(rows),
        "source_universe_sha256": sha256_bytes(universe_bytes),
    }
    sampling_manifest_path = OUT / "sampling_manifest.json"
    sampling_manifest_path.write_text(json.dumps(planned_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_document[row["document_filename"]].append(row)
    if set(by_document) != set(ALLOCATION):
        raise RuntimeError("capture universe documents do not match fixed allocation")

    selected_ids: set[str] = set()
    quotas_by_document: dict[str, dict[str, int]] = {}
    for filename, target in ALLOCATION.items():
        chosen, quotas = select_document(by_document[filename], target, filename)
        selected_ids.update(chosen)
        quotas_by_document[filename] = quotas
    if len(selected_ids) != sum(ALLOCATION.values()):
        raise RuntimeError("sample size does not match fixed allocation")

    selected_lines = [line for line, row in zip(original_lines, rows) if row["case_id"] in selected_ids]
    selected_rows = [row for row in rows if row["case_id"] in selected_ids]
    sample_path = OUT / "external_evaluation_sample_v1.jsonl"
    sample_path.write_bytes(b"".join(selected_lines))
    sample_sha256 = sha256_bytes(sample_path.read_bytes())

    source_set = json.loads(SOURCE_SET.read_text(encoding="utf-8"))
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    per_doc = Counter(row["document_filename"] for row in selected_rows)
    per_risk = Counter(risk_type(row) for row in selected_rows)
    per_doc_risk = {
        filename: dict(sorted(Counter(risk_type(row) for row in selected_rows if row["document_filename"] == filename).items()))
        for filename in sorted(ALLOCATION)
    }
    metadata = {
        "schema_version": "external_evaluation_sample_v1",
        "freeze_status": "FROZEN_BEFORE_GOLD_ANNOTATION",
        "source_pipeline_run_id": provenance["pipeline_run_id"],
        "capture_universe_count": len(rows),
        "capture_universe_sha256": sha256_bytes(universe_bytes),
        "sample_size": len(selected_rows),
        "sample_sha256": sample_sha256,
        "source_documents": [
            {
                "document_id": source["document_id"],
                "filename": source["filename"],
                "original_sha256": source["original_sha256"],
                "normalized_text_sha256": source["normalized_text_sha256"],
            }
            for source in source_set["sources"]
        ],
        "per_document_sample_count": dict(sorted(per_doc.items())),
        "per_risk_type_distribution": dict(sorted(per_risk.items())),
        "per_document_risk_type_distribution": per_doc_risk,
        "sampling_seed": SEED,
        "sampling_algorithm_version": ALGORITHM_VERSION,
        "sampling_algorithm_fingerprint": algorithm_fingerprint,
        "judge_invocation_count": 0,
        "ranking_provenance": "RRF retained for all cases; CrossEncoder success count was zero",
        "annotation_status": "UNLABELED",
    }
    (OUT / "external_evaluation_sample_v1.metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    universe_manifest = {
        "schema_version": "external_holdout_capture_universe_manifest_v1",
        "immutable": True,
        "pipeline_run_id": provenance["pipeline_run_id"],
        "capture_universe_path": str(UNIVERSE.relative_to(ROOT)).replace("\\", "/"),
        "case_count": len(rows),
        "capture_universe_sha256": sha256_bytes(universe_bytes),
        "ordered_case_ids_sha256": canonical_hash([row["case_id"] for row in rows]),
        "per_document_count": dict(sorted(Counter(row["document_filename"] for row in rows).items())),
        "judge_invocation_count": 0,
    }
    (OUT / "capture_universe_manifest.json").write_text(json.dumps(universe_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    annotation_path = OUT / "annotation_review_sample_v1.jsonl"
    with annotation_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected_rows:
            annotation = dict(row)
            annotation.update({
                "gold_label": None,
                "adjudicated_label": None,
                "reviewed": False,
                "reviewer_notes": None,
                "unresolved": False,
            })
            handle.write(json.dumps(annotation, ensure_ascii=False, separators=(",", ":")) + "\n")

    completed_manifest = {
        **planned_manifest,
        "status": "COMPLETED_BEFORE_ANNOTATION",
        "sample_size": len(selected_rows),
        "sample_sha256": sample_sha256,
        "selected_case_ids_sha256": canonical_hash([row["case_id"] for row in selected_rows]),
        "per_document_quotas_by_risk_type": quotas_by_document,
        "judge_invocation_count": 0,
    }
    sampling_manifest_path.write_text(json.dumps(completed_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "SAMPLE_FROZEN_BEFORE_GOLD_ANNOTATION",
        "capture_universe_count": len(rows),
        "capture_universe_sha256": sha256_bytes(universe_bytes),
        "sample_size": len(selected_rows),
        "sample_sha256": sample_sha256,
        "per_document_sample_count": dict(sorted(per_doc.items())),
        "sampling_seed": SEED,
        "sampling_algorithm_fingerprint": algorithm_fingerprint,
        "judge_invocation_count": 0,
        "output_dir": str(OUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
