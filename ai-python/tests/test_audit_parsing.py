from services.audit_agent import _extract_json_object, _extract_snippet, _split_vector_documents
from langchain_core.documents import Document


def test_extract_json_from_markdown_response():
    parsed = _extract_json_object('result:\n```json\n{"riskItems":[{"level":"HIGH"}]}\n```')
    assert parsed == {"riskItems": [{"level": "HIGH"}]}


def test_extract_json_returns_none_for_invalid_model_output():
    assert _extract_json_object("rate limited, retry later") is None


def test_extract_snippet_keeps_matching_contract_context():
    text = "付款周期为三十日。逾期付款每日承担违约金。争议由法院管辖。"
    snippet = _extract_snippet(text, "违约金", max_len=20)
    assert "违约金" in snippet


def test_split_vector_documents_preserves_metadata():
    docs = [Document(page_content="第一条 " * 200, metadata={"page": 1})]
    chunks = _split_vector_documents(docs, chunk_size=120, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(chunk.metadata["page"] == 1 for chunk in chunks)
