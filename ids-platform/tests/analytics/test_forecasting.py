"""Tests for forecasting.py."""

from backend.analytics.forecasting import forecast_next_days


def test_empty_input_returns_empty_forecast():
    assert forecast_next_days([]) == []


def test_single_data_point_forecasts_flat():
    result = forecast_next_days([{"date": "2026-07-01", "count": 10}], days_ahead=3)
    assert len(result) == 3
    assert all(point["count"] == 10.0 for point in result)


def test_forecast_continues_an_upward_trend():
    data = [
        {"date": "2026-07-01", "count": 10},
        {"date": "2026-07-02", "count": 20},
        {"date": "2026-07-03", "count": 30},
    ]
    result = forecast_next_days(data, days_ahead=2)
    assert result[0]["count"] == 40.0
    assert result[1]["count"] == 50.0


def test_forecast_dates_continue_sequentially():
    data = [{"date": "2026-07-01", "count": 5}, {"date": "2026-07-02", "count": 5}]
    result = forecast_next_days(data, days_ahead=2)
    assert result[0]["date"] == "2026-07-03"
    assert result[1]["date"] == "2026-07-04"


def test_forecast_never_projects_a_negative_count():
    data = [
        {"date": "2026-07-01", "count": 10},
        {"date": "2026-07-02", "count": 5},
        {"date": "2026-07-03", "count": 0},
    ]
    result = forecast_next_days(data, days_ahead=5)
    assert all(point["count"] >= 0 for point in result)
