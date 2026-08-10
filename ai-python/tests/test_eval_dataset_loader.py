import json

import pytest

from eval.dataset_loader import DatasetValidationError, load_dataset


def _case(case_id="case-1"):
    return {
        "case_id": case_id,
        "document_id": "doc-1",
        "query": "payment penalty",
        "expected_evidence": [{"page": 2, "text": "payment penalty"}],
        "metadata": {"source_type": "synthetic"},
    }


def test_load_valid_dataset(tmp_path):
    path = tmp_path / "valid.jsonl"
    path.write_text(json.dumps(_case()) + "\n", encoding="utf-8")
    cases = load_dataset(path)
    assert cases[0].case_id == "case-1"
    assert cases[0].expected_evidence[0].page == 2


def test_invalid_json_has_file_and_line(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text(json.dumps(_case()) + "\nnot-json\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError, match=r"invalid\.jsonl.*line 2.*invalid JSON"):
        load_dataset(path)


def test_missing_required_field_includes_case_id(tmp_path):
    value = _case()
    del value["query"]
    path = tmp_path / "missing.jsonl"
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError, match=r"line 1.*case-1.*query"):
        load_dataset(path)


def test_duplicate_case_id_is_rejected(tmp_path):
    path = tmp_path / "duplicate.jsonl"
    path.write_text(
        "\n".join(json.dumps(_case()) for _ in range(2)) + "\n", encoding="utf-8"
    )
    with pytest.raises(DatasetValidationError, match=r"line 2.*duplicate case_id"):
        load_dataset(path)
