"""Validate human adjudication and freeze External Holdout V1 without invoking a Judge."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SAMPLE_DIR = ROOT / "ai-python/eval/experiments/external_holdout_20260824/adjudication_sample_v1"
SAMPLE_PATH = SAMPLE_DIR / "external_evaluation_sample_v1.jsonl"
ANNOTATION_PATH = SAMPLE_DIR / "annotation_review_sample_v1.jsonl"
SAMPLE_METADATA_PATH = SAMPLE_DIR / "external_evaluation_sample_v1.metadata.json"
SAMPLING_MANIFEST_PATH = SAMPLE_DIR / "sampling_manifest.json"
UNIVERSE_MANIFEST_PATH = SAMPLE_DIR / "capture_universe_manifest.json"
OUT = ROOT / "ai-python/eval/judge/external_holdout_v1"
LABELS = {"SUPPORTED", "PARTIAL", "UNSUPPORTED"}
REVIEW_FIELDS = {"gold_label", "adjudicated_label", "reviewed", "reviewer_notes", "unresolved"}
FORBIDDEN_JUDGE_KEYS = {
    "predicted_label", "v0_prediction", "v1_prediction", "v2_prediction", "v2_1_prediction",
    "judge", "judge_reason", "judge_confidence",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in rows) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def collect_keys(value: object, keys: set[str]) -> None:
    if isinstance(value, dict):
        keys.update(str(key).lower() for key in value)
        for child in value.values():
            collect_keys(child, keys)
    elif isinstance(value, list):
        for child in value:
            collect_keys(child, keys)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unavailable"


def validate() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    errors: list[str] = []
    sample = load_rows(SAMPLE_PATH)
    annotation = load_rows(ANNOTATION_PATH)
    sample_metadata = json.loads(SAMPLE_METADATA_PATH.read_text(encoding="utf-8"))
    sampling_manifest = json.loads(SAMPLING_MANIFEST_PATH.read_text(encoding="utf-8"))
    universe_manifest = json.loads(UNIVERSE_MANIFEST_PATH.read_text(encoding="utf-8"))

    sample_sha = sha256(SAMPLE_PATH)
    if len(sample) != 120 or len(annotation) != 120:
        errors.append(f"expected 120 sample/annotation rows, got {len(sample)}/{len(annotation)}")
    if sample_sha != sample_metadata.get("sample_sha256") or sample_sha != sampling_manifest.get("sample_sha256"):
        errors.append("source sample SHA256 mismatch")
    if sampling_manifest.get("status") != "COMPLETED_BEFORE_ANNOTATION":
        errors.append("sampling manifest is not frozen before annotation")
    if sampling_manifest.get("judge_invocation_count") != 0 or sample_metadata.get("judge_invocation_count") != 0:
        errors.append("source metadata reports Judge invocation")
    if universe_manifest.get("immutable") is not True or universe_manifest.get("case_count") != 289:
        errors.append("capture universe provenance invalid")
    if universe_manifest.get("capture_universe_sha256") != sample_metadata.get("capture_universe_sha256"):
        errors.append("universe SHA256 provenance mismatch")

    if [row.get("case_id") for row in sample] != [row.get("case_id") for row in annotation]:
        errors.append("sample membership/order differs from frozen sample")
    if len({row.get("case_id") for row in annotation}) != len(annotation):
        errors.append("duplicate case_id")

    for index, (source, reviewed) in enumerate(zip(sample, annotation), start=1):
        immutable = {key: value for key, value in reviewed.items() if key not in REVIEW_FIELDS}
        if immutable != source:
            errors.append(f"line {index} {reviewed.get('case_id')}: immutable capture fields changed")
        if reviewed.get("reviewed") is not True:
            errors.append(f"line {index} {reviewed.get('case_id')}: not reviewed")
        if reviewed.get("unresolved") is not False:
            errors.append(f"line {index} {reviewed.get('case_id')}: unresolved")
        if reviewed.get("gold_label") not in LABELS:
            errors.append(f"line {index} {reviewed.get('case_id')}: invalid gold label")
        if reviewed.get("adjudicated_label") != reviewed.get("gold_label"):
            errors.append(f"line {index} {reviewed.get('case_id')}: adjudicated/gold mismatch")
        keys: set[str] = set()
        collect_keys(reviewed, keys)
        leaked = FORBIDDEN_JUDGE_KEYS & keys
        if leaked:
            errors.append(f"line {index} {reviewed.get('case_id')}: forbidden Judge keys {sorted(leaked)}")

    audit = {
        "status": "PASS" if not errors else "FAIL",
        "total": len(annotation),
        "reviewed": sum(row.get("reviewed") is True for row in annotation),
        "draft": sum(row.get("reviewed") is not True for row in annotation),
        "unresolved": sum(row.get("unresolved") is True for row in annotation),
        "source_sample_sha256": sample_sha,
        "source_sample_sha256_match": sample_sha == sample_metadata.get("sample_sha256") == sampling_manifest.get("sample_sha256"),
        "capture_universe_sha256": universe_manifest.get("capture_universe_sha256"),
        "membership_match": [row.get("case_id") for row in sample] == [row.get("case_id") for row in annotation],
        "immutable_fields_match": not any("immutable capture fields changed" in error for error in errors),
        "judge_invocation_count": 0,
        "errors": errors,
    }
    return annotation, audit


def main() -> None:
    rows, audit = validate()
    if audit["status"] != "PASS":
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    dataset_path = OUT / "external_holdout_v1.jsonl"
    with dataset_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    dataset_sha = sha256(dataset_path)
    if dataset_sha != canonical_hash(rows):
        raise RuntimeError("canonical dataset hash mismatch")

    label_distribution = dict(Counter(row["gold_label"] for row in rows))
    per_document: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        per_document[row["document_filename"]][row["gold_label"]] += 1
    risk_distribution = dict(sorted(Counter(str((row.get("claim") or {}).get("riskType") or "UNKNOWN") for row in rows).items()))
    sample_metadata = json.loads(SAMPLE_METADATA_PATH.read_text(encoding="utf-8"))
    sampling_manifest = json.loads(SAMPLING_MANIFEST_PATH.read_text(encoding="utf-8"))
    universe_manifest = json.loads(UNIVERSE_MANIFEST_PATH.read_text(encoding="utf-8"))
    metadata = {
        "schema_version": "external_holdout_v1",
        "freeze_status": "EXTERNAL_HOLDOUT_V1_FROZEN",
        "dataset_sha256": dataset_sha,
        "dataset_hash_method": "SHA256 of UTF-8 canonical JSONL; sorted keys, compact separators, LF newline",
        "case_count": len(rows),
        "label_distribution": label_distribution,
        "per_document_label_distribution": {key: dict(value) for key, value in sorted(per_document.items())},
        "risk_type_distribution": risk_distribution,
        "reviewed_count": len(rows),
        "draft_count": 0,
        "unresolved_count": 0,
        "reviewer_notes_coverage": sum(bool(row.get("reviewer_notes")) for row in rows) / len(rows),
        "adjudication_coverage": 1.0,
        "source_pipeline_run_id": sample_metadata["source_pipeline_run_id"],
        "source_sample_sha256": sample_metadata["sample_sha256"],
        "capture_universe_sha256": universe_manifest["capture_universe_sha256"],
        "sampling_seed": sampling_manifest["sampling_seed"],
        "sampling_algorithm_fingerprint": sampling_manifest["sampling_algorithm_fingerprint"],
        "source_document_hashes": sample_metadata["source_documents"],
        "source_commit": git_head(),
        "judge_invocation_count": 0,
    }
    (OUT / "external_holdout_v1.metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "status": "PASS",
        "dataset_sha256": dataset_sha,
        "total": len(rows),
        "reviewed": len(rows),
        "draft": 0,
        "unresolved": 0,
        "label_distribution": label_distribution,
        "per_document_label_distribution": metadata["per_document_label_distribution"],
        "risk_type_distribution": risk_distribution,
        "reviewer_notes_coverage": metadata["reviewer_notes_coverage"],
        "adjudication_coverage": 1.0,
        "integrity_comparison": audit,
        "judge_invocation_count": 0,
    }
    (OUT / "adjudication_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    freeze = {
        "schema_version": "external_holdout_freeze_manifest_v1",
        "status": "EXTERNAL_HOLDOUT_V1_FROZEN",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path.relative_to(ROOT)).replace("\\", "/"),
        "dataset_sha256": dataset_sha,
        "metadata_sha256": sha256(OUT / "external_holdout_v1.metadata.json"),
        "adjudication_summary_sha256": sha256(OUT / "adjudication_summary.json"),
        "source_sample_sha256": sample_metadata["sample_sha256"],
        "sampling_manifest_sha256": sha256(SAMPLING_MANIFEST_PATH),
        "capture_universe_manifest_sha256": sha256(UNIVERSE_MANIFEST_PATH),
        "capture_universe_sha256": universe_manifest["capture_universe_sha256"],
        "judge_invocation_count": 0,
    }
    (OUT / "freeze_manifest.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": freeze["status"], "dataset_sha256": dataset_sha, "label_distribution": label_distribution, "output_dir": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
