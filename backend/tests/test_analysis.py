"""Offline unit tests for the pure analysis functions (synthetic fixtures)."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import analysis  # noqa: E402

DELIVERY = date(2026, 1, 15)  # deadline: 2026-01-14 09:50 UTC at default cutoff


def fc(start: str, publish: str, gen: float) -> dict:
    return {"startTime": start, "publishTime": publish, "generation": gen}


def test_point_in_time_never_picks_post_deadline_forecast():
    rows = [
        fc("2026-01-15T00:00:00Z", "2026-01-14T09:30:00Z", 1000.0),  # eligible, latest before gate
        fc("2026-01-15T00:00:00Z", "2026-01-14T07:30:00Z", 900.0),   # eligible, earlier
        fc("2026-01-15T00:00:00Z", "2026-01-14T11:30:00Z", 5000.0),  # AFTER deadline — must not be selected
        fc("2026-01-15T00:00:00Z", "2026-01-14T09:50:00Z", 7777.0),  # exactly AT deadline — strictly-before rule excludes it
    ]
    selected = analysis.select_decision_forecasts(rows, DELIVERY, "09:50")
    hour0 = selected[0]
    assert hour0["forecast"] == 1000.0
    assert hour0["publishTime"].isoformat().startswith("2026-01-14T09:30")
    # The leaky latest-ever value is the post-deadline one, kept separate.
    assert hour0["leakyForecast"] == 5000.0


def test_point_in_time_cutoff_changes_selection():
    rows = [
        fc("2026-01-15T00:00:00Z", "2026-01-14T09:30:00Z", 1000.0),
        fc("2026-01-15T00:00:00Z", "2026-01-14T04:30:00Z", 800.0),
    ]
    assert analysis.select_decision_forecasts(rows, DELIVERY, "09:50")[0]["forecast"] == 1000.0
    assert analysis.select_decision_forecasts(rows, DELIVERY, "05:00")[0]["forecast"] == 800.0


def test_hourly_averaging():
    rows = [
        {"startTime": "2026-01-15T00:00:00Z", "fuelType": "WIND", "generation": 1000},
        {"startTime": "2026-01-15T00:30:00Z", "fuelType": "WIND", "generation": 1400},
        {"startTime": "2026-01-15T01:00:00Z", "fuelType": "WIND", "generation": 2000},
        {"startTime": "2026-01-15T01:30:00Z", "fuelType": "WIND", "generation": 2000},
        {"startTime": "2026-01-15T01:00:00Z", "fuelType": "CCGT", "generation": 99999},  # ignored
    ]
    hourly = analysis.hourly_actuals(rows)
    assert len(hourly) == 2
    assert hourly[0]["generation"] == 1200.0
    assert hourly[1]["generation"] == 2000.0
    assert hourly[0]["nHalfHours"] == 2


def test_metrics_hand_computable():
    # forecast/actual pairs: errors +100, -100, +200
    m = analysis.metrics([(1100.0, 1000.0), (900.0, 1000.0), (1200.0, 1000.0)])
    assert m["n"] == 3
    assert m["mae"] == 133.3
    assert m["bias"] == 66.7
    assert m["meanActual"] == 1000.0
    assert m["nmae"] == 0.1333
    assert m["overForecastHours"] == 2
    assert m["underForecastHours"] == 1
    # RMSE = sqrt((100^2 + 100^2 + 200^2)/3) = sqrt(20000) = 141.42 -> 141.4
    assert m["rmse"] == 141.4
    # Cumulative energy error = (100 - 100 + 200) MWh = 0.2 GWh
    assert m["cumulativeEnergyErrorGWh"] == 0.2


def test_metrics_perfect_forecast():
    m = analysis.metrics([(1000.0, 1000.0), (2000.0, 2000.0)])
    assert m["mae"] == 0.0 and m["rmse"] == 0.0 and m["bias"] == 0.0
    assert m["correlation"] == 1.0
    assert m["mape"] == 0.0


def test_metrics_empty():
    m = analysis.metrics([])
    assert m["n"] == 0 and m["mae"] is None


def test_deadline_is_day_before_at_cutoff():
    dl = analysis.decision_deadline(date(2026, 1, 15), "09:50")
    assert dl.isoformat() == "2026-01-14T09:50:00+00:00"
    dl2 = analysis.decision_deadline(date(2026, 1, 1), "09:50")
    assert dl2.isoformat() == "2025-12-31T09:50:00+00:00"


def test_lead_hours_for_default_gate():
    rows = [fc("2026-01-15T00:00:00Z", "2026-01-14T09:30:00Z", 1000.0)]
    sel = analysis.select_decision_forecasts(rows, DELIVERY, "09:50")[0]
    assert sel["leadHours"] == 14.5
