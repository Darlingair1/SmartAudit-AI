from core.config import Settings
from services.retrieval_hybrid import (
    _build_parent_text_and_segments,
    _chroma_security_filter,
    _encode_chroma_metadata,
    _decode_page_nos_metadata,
    _encode_page_nos_metadata,
    _page_nos_for_interval,
    build_parent_child_chunks,
)
from services.v3_types import RetrievalCandidate, SecurityContext


def _settings(*, overlap_tokens: int = 0) -> Settings:
    return Settings(
        parent_chunk_min_tokens=100,
        parent_chunk_max_tokens=1000,
        child_chunk_size_tokens=80,
        child_chunk_overlap_tokens=overlap_tokens,
    )


def _chunks(page_texts: list[str], *, overlap_tokens: int = 0):
    security = SecurityContext(
        tenant_id="test",
        org_id="test",
        user_id="test",
        permission_scope="test",
        task_id="page-mapping",
        document_id="document",
        contract_id="contract",
    )
    return build_parent_child_chunks(
        page_texts,
        security,
        _settings(overlap_tokens=overlap_tokens),
        {"parse_quality": "GOOD"},
    )


def _two_page_texts() -> list[str]:
    return ["A" * 150, "B" * 300]


def test_child_fully_on_first_page_has_single_page_metadata() -> None:
    _, children = _chunks(_two_page_texts())
    child = children[0]
    assert child.offset_start == 0
    assert child.page_nos == [1]
    assert (child.page_no, child.page_start, child.page_end) == (1, 1, 1)


def test_child_on_second_page_front_with_marker_maps_to_second_page() -> None:
    _, children = _chunks(_two_page_texts())
    child = children[1]
    assert child.text.startswith("[Page 2]")
    assert child.page_nos == [2]
    assert (child.page_no, child.page_start, child.page_end) == (2, 2, 2)


def test_child_on_second_page_back_without_marker_maps_to_second_page() -> None:
    _, children = _chunks(_two_page_texts())
    child = children[2]
    assert "[Page 2]" not in child.text
    assert child.page_nos == [2]
    assert (child.page_no, child.page_start, child.page_end) == (2, 2, 2)


def test_child_crossing_page_boundary_contains_both_pages() -> None:
    _, children = _chunks(_two_page_texts(), overlap_tokens=30)
    child = children[1]
    assert child.offset_start == 100
    assert child.page_nos == [1, 2]
    assert (child.page_no, child.page_start, child.page_end) == (1, 1, 2)


def test_later_parent_second_page_backs_do_not_fallback_to_parent_start() -> None:
    pages = ["A" * 150, "B" * 300, "C" * 150, "D" * 300, "E" * 150, "F" * 300]
    parents, children = _chunks(pages)
    assert [(p.page_start, p.page_end) for p in parents] == [(1, 2), (3, 4), (5, 6)]

    page_four_back = next(
        child for child in children if child.parent_id == "p-0002" and child.offset_start == 320
    )
    page_six_back = next(
        child for child in children if child.parent_id == "p-0003" and child.offset_start == 320
    )
    assert page_four_back.page_nos == [4]
    assert page_four_back.page_no == 4
    assert page_six_back.page_nos == [6]
    assert page_six_back.page_no == 6


def test_empty_page_does_not_fill_non_contiguous_page_nos() -> None:
    parents, children = _chunks(["A" * 150, "", "C" * 300], overlap_tokens=30)
    assert len(parents) == 1
    assert (parents[0].page_start, parents[0].page_end) == (1, 3)
    crossing = children[1]
    assert crossing.page_nos == [1, 3]
    assert 2 not in crossing.page_nos


def test_page_segments_cover_body_not_page_marker() -> None:
    combined, segments = _build_parent_text_and_segments([(1, "abc"), (2, "def")])
    assert combined == "[Page 1] abc\n[Page 2] def"
    assert combined[segments[0].start_offset : segments[0].end_offset] == "abc"
    assert combined[segments[1].start_offset : segments[1].end_offset] == "def"

    second_marker_start = combined.index("[Page 2]")
    assert _page_nos_for_interval(
        segments, second_marker_start, segments[1].start_offset
    ) == []


def test_chunk_text_boundaries_ids_and_count_are_unchanged() -> None:
    parents, children = _chunks(_two_page_texts())
    combined = "[Page 1] " + "A" * 150 + "\n[Page 2] " + "B" * 300
    assert parents[0].text == combined
    assert [child.child_id for child in children] == [
        "c-0001-0001",
        "c-0001-0002",
        "c-0001-0003",
    ]
    assert [(child.offset_start, child.offset_end) for child in children] == [
        (0, 160),
        (160, 320),
        (320, len(combined)),
    ]
    assert [child.text for child in children] == [
        combined[0:160].strip(),
        combined[160:320].strip(),
        combined[320:].strip(),
    ]


def test_chroma_page_nos_json_round_trip_is_canonical() -> None:
    from chromadb.api.types import validate_metadata

    encoded = _encode_page_nos_metadata([4, 3, 4])
    assert encoded == "[3,4]"
    assert validate_metadata({"page_nos": encoded}) == {"page_nos": "[3,4]"}
    assert _decode_page_nos_metadata(encoded, fallback_page_no=9) == [3, 4]


def test_chroma_page_nos_legacy_fallback_uses_page_no() -> None:
    assert _decode_page_nos_metadata(None, fallback_page_no=5) == [5]
    assert _decode_page_nos_metadata("", fallback_page_no="6") == [6]


def test_chroma_metadata_encoder_drops_none_and_preserves_scalars() -> None:
    encoded = _encode_chroma_metadata(
        {
            "chapter_no": None,
            "page_nos": [4, 3, 4],
            "page_no": 3,
            "score": 0.0,
            "enabled": False,
            "title": "clause",
        }
    )
    assert encoded == {
        "page_nos": "[3,4]",
        "page_no": 3,
        "score": 0.0,
        "enabled": False,
        "title": "clause",
    }


def test_chroma_metadata_encoder_rejects_unexpected_complex_values() -> None:
    import pytest

    with pytest.raises(TypeError, match="unsupported Chroma metadata type"):
        _encode_chroma_metadata({"unexpected": {"nested": True}})


def test_chroma_security_filter_uses_explicit_and_operator() -> None:
    from chromadb.api.types import validate_where

    security = SecurityContext(
        tenant_id="tenant-a",
        org_id="org-a",
        user_id="user-a",
        permission_scope="test",
        task_id="task-a",
        document_id="document-a",
        contract_id="contract-a",
    )
    where = _chroma_security_filter(security)
    assert where == {
        "$and": [
            {"tenant_id": {"$eq": "tenant-a"}},
            {"task_id": {"$eq": "task-a"}},
        ]
    }
    validate_where(where)


def test_retrieval_candidate_page_nos_default_factory_is_not_shared() -> None:
    first = RetrievalCandidate("c1", "p1", "ch1", 1, "", "", "one")
    second = RetrievalCandidate("c2", "p1", "ch2", 1, "", "", "two")
    first.page_nos.append(1)
    assert second.page_nos == []
