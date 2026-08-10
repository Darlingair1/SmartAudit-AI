import hashlib
import json

import pytest

from eval.validate_benchmark import BenchmarkValidationError, validate_benchmark


def _files(tmp_path, *, evidence="payment is due", manifest_hash=None, document=True):
    document_path = tmp_path / "contract.md"
    if document:
        document_path.write_text("payment is due within ten days", encoding="utf-8")
    digest = manifest_hash or (
        hashlib.sha256(document_path.read_bytes()).hexdigest() if document else "0" * 64
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_version": "v1",
                "documents": [
                    {
                        "document_id": "doc-1",
                        "path": "contract.md",
                        "source_type": "synthetic",
                        "sha256": digest,
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "document_id": "doc-1",
                "query": "when is payment due",
                "expected_evidence": [{"page": 1, "text": evidence}],
                "metadata": {
                    "source_type": "synthetic",
                    "annotation_status": "reviewed",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return dataset, manifest


def test_manifest_and_gold_validation(tmp_path):
    dataset, manifest = _files(tmp_path)
    result = validate_benchmark(dataset, manifest)
    assert result["status"] == "valid"
    assert result["document_count"] == 1
    assert result["reviewed_case_count"] == 1


def test_missing_document_is_rejected(tmp_path):
    dataset, manifest = _files(tmp_path, document=False)
    with pytest.raises(BenchmarkValidationError, match="document not found"):
        validate_benchmark(dataset, manifest)


def test_hash_mismatch_is_rejected(tmp_path):
    dataset, manifest = _files(tmp_path, manifest_hash="0" * 64)
    with pytest.raises(BenchmarkValidationError, match="SHA256 mismatch"):
        validate_benchmark(dataset, manifest)


def test_gold_missing_from_document_is_rejected(tmp_path):
    dataset, manifest = _files(tmp_path, evidence="not present anywhere")
    with pytest.raises(BenchmarkValidationError, match="cannot be located"):
        validate_benchmark(dataset, manifest)
