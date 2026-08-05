"""Tests for feature_mapper.map_to_model_features()."""

from backend.packet_capture.feature_mapper import DEFAULT_FILL_VALUE, map_to_model_features


def test_all_expected_features_present_are_matched():
    live = {"Flow Duration": 100.0, "Total Fwd Packets": 3.0}
    mapped, report = map_to_model_features(live, ["Flow Duration", "Total Fwd Packets"])

    assert mapped == {"Flow Duration": 100.0, "Total Fwd Packets": 3.0}
    assert report.matched == ["Flow Duration", "Total Fwd Packets"]
    assert report.filled_with_default == []
    assert report.coverage_ratio == 1.0


def test_missing_expected_feature_is_defaulted():
    live = {"Flow Duration": 100.0}
    mapped, report = map_to_model_features(live, ["Flow Duration", "Init_Win_bytes_forward"])

    assert mapped["Init_Win_bytes_forward"] == DEFAULT_FILL_VALUE
    assert report.filled_with_default == ["Init_Win_bytes_forward"]
    assert report.coverage_ratio == 0.5


def test_output_order_matches_expected_features_order():
    live = {"b": 2.0, "a": 1.0}
    mapped, _ = map_to_model_features(live, ["a", "b"])
    assert list(mapped.keys()) == ["a", "b"]


def test_unused_live_features_are_reported_as_dropped():
    live = {"a": 1.0, "unused_feature": 99.0}
    mapped, report = map_to_model_features(live, ["a"])

    assert "unused_feature" not in mapped
    assert report.dropped_unused == ["unused_feature"]


def test_empty_expected_features_produces_empty_mapping():
    mapped, report = map_to_model_features({"a": 1.0}, [])
    assert mapped == {}
    assert report.coverage_ratio == 1.0  # vacuously full coverage of an empty requirement


def test_full_default_fill_gives_zero_coverage():
    mapped, report = map_to_model_features({}, ["x", "y", "z"])
    assert all(v == DEFAULT_FILL_VALUE for v in mapped.values())
    assert report.coverage_ratio == 0.0
