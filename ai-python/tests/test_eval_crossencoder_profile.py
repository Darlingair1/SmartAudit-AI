from eval.profile_crossencoder import _batches, _percentile, distribution


def test_profile_distribution_reports_required_percentiles() -> None:
    assert distribution([1, 2, 3, 10]) == {
        "mean": 4.0,
        "p50": 3.0,
        "p95": 10.0,
        "max": 10.0,
    }


def test_profile_distribution_handles_empty_samples() -> None:
    assert distribution([]) == {
        "mean": None,
        "p50": None,
        "p95": None,
        "max": None,
    }


def test_profile_batches_preserve_all_values() -> None:
    assert list(_batches([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_profile_percentile_uses_nearest_rank_index() -> None:
    assert _percentile([10, 20, 30, 40], 0.5) == 30.0
    assert _percentile([], 0.95) is None
