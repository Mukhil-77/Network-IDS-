"""
A simple, honest forecast of near-future threat volume from recent daily
counts - linear least-squares extrapolation, nothing more sophisticated.
This is deliberately NOT presented as a serious predictive model: SOC
capacity planning ("should we expect more or fewer alerts next week")
is a reasonable use for a simple trend line; anything claiming more
precision than that would be overclaiming what a few dozen daily counts
can actually support statistically.
"""

from __future__ import annotations


def forecast_next_days(daily_counts: list[dict], days_ahead: int = 7) -> list[dict]:
    """
    `daily_counts`: [{"date": "2026-07-01", "count": 12}, ...] (e.g. from
    trends.attack_timeline()), assumed already sorted by date.

    Returns `days_ahead` projected {"date": ..., "count": ...} points,
    continuing the sequence of dates in `daily_counts`. Falls back to
    "flat" (repeat the last known value) if there's fewer than 2 data
    points - a trend line through 0 or 1 points isn't meaningful.
    """
    if not daily_counts:
        return []

    counts = [d["count"] for d in daily_counts]
    n = len(counts)

    if n < 2:
        last_count = counts[-1]
        slope, intercept = 0.0, float(last_count)
    else:
        # Ordinary least squares over x = 0..n-1 - no numpy dependency
        # needed for a fit this simple.
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(counts) / n
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, counts))
        denominator = sum((x - mean_x) ** 2 for x in xs)
        slope = numerator / denominator if denominator else 0.0
        intercept = mean_y - slope * mean_x

    from datetime import datetime, timedelta

    last_date = datetime.strptime(daily_counts[-1]["date"], "%Y-%m-%d")
    projections = []
    for step in range(1, days_ahead + 1):
        projected_count = max(0.0, slope * (n - 1 + step) + intercept)
        projections.append({
            "date": (last_date + timedelta(days=step)).strftime("%Y-%m-%d"),
            "count": round(projected_count, 1),
        })
    return projections
