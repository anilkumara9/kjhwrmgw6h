"""Pure analysis functions — no network, fully unit-testable.

Implements the point-in-time rule at the heart of the app:
for a delivery day D and a decision deadline (default 09:50 on D-1),
the *decision forecast* for each delivery hour is the forecast with the
greatest publishTime STRICTLY BEFORE the deadline. Forecasts published
after the deadline must never be used for the decision view — using them
is look-ahead leakage. The latest-ever forecast is computed separately,
only as a clearly-labelled leakage comparison.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone


def parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp into an aware UTC datetime."""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_cutoff(cutoff: str) -> time:
    """Validate and parse an HH:MM cutoff string."""
    parts = str(cutoff).strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid cutoff {cutoff!r}; expected HH:MM")
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError(f"Invalid cutoff {cutoff!r}; expected HH:MM") from exc
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"Invalid cutoff {cutoff!r}; hour 0-23, minute 0-59")
    return time(hour=hh, minute=mm)


def decision_deadline(delivery_date: date, cutoff: str = "09:50") -> datetime:
    """Decision deadline for a delivery day: cutoff time on D-1 (UTC).

    January in the UK is GMT, so UK time == UTC with no DST complication.
    """
    cutoff_time = parse_cutoff(cutoff)
    day_before = delivery_date - timedelta(days=1)
    return datetime.combine(day_before, cutoff_time, tzinfo=timezone.utc)


def hourly_actuals(half_hourly_rows: list[dict]) -> list[dict]:
    """Aggregate half-hourly FUELHH wind rows to hourly means.

    Each hour is the mean of the two half-hours starting at :00 and :30.
    Returns a sorted list of {startTime (ISO, hour start), generation}.
    Rows for other fuel types are ignored when a fuelType field is present.
    """
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for row in half_hourly_rows:
        if row.get("fuelType") is not None and row.get("fuelType") != "WIND":
            continue
        start = parse_ts(row["startTime"])
        hour_start = start.replace(minute=0, second=0, microsecond=0)
        buckets[hour_start].append(float(row["generation"]))
    result = []
    for hour_start in sorted(buckets):
        values = buckets[hour_start]
        result.append(
            {
                "startTime": hour_start.isoformat().replace("+00:00", "Z"),
                "generation": sum(values) / len(values),
                "nHalfHours": len(values),
            }
        )
    return result


def _index_forecasts(forecast_rows: list[dict]) -> dict[datetime, list[dict]]:
    by_start: dict[datetime, list[dict]] = defaultdict(list)
    for row in forecast_rows:
        start = parse_ts(row["startTime"]).replace(minute=0, second=0, microsecond=0)
        by_start[start].append(
            {
                "startTime": start,
                "publishTime": parse_ts(row["publishTime"]),
                "generation": float(row["generation"]),
            }
        )
    for entries in by_start.values():
        entries.sort(key=lambda e: e["publishTime"])
    return by_start


def select_decision_forecasts(
    forecast_rows: list[dict],
    delivery_date: date,
    cutoff: str = "09:50",
) -> list[dict]:
    """Point-in-time selection for one delivery day.

    For each delivery hour, pick the forecast with the greatest publishTime
    strictly before the decision deadline. Also returns the latest-ever
    (leaky) forecast per hour for comparison only.
    """
    deadline = decision_deadline(delivery_date, cutoff)
    by_start = _index_forecasts(forecast_rows)
    results = []
    for hour in range(24):
        start = datetime.combine(delivery_date, time(hour=hour), tzinfo=timezone.utc)
        entries = by_start.get(start, [])
        eligible = [e for e in entries if e["publishTime"] < deadline]
        decision = eligible[-1] if eligible else None
        latest = entries[-1] if entries else None
        results.append(
            {
                "startTime": start,
                "deadline": deadline,
                "forecast": decision["generation"] if decision else None,
                "publishTime": decision["publishTime"] if decision else None,
                "leadHours": (
                    (start - decision["publishTime"]).total_seconds() / 3600.0
                    if decision
                    else None
                ),
                "leakyForecast": latest["generation"] if latest else None,
                "leakyPublishTime": latest["publishTime"] if latest else None,
            }
        )
    return results


def metrics(pairs: list[tuple[float, float]]) -> dict:
    """Accuracy metrics for aligned (forecast, actual) pairs.

    bias = mean(forecast - actual); positive bias = systematic over-forecast.
    Cumulative energy error: hourly MW error x 1h = MWh, summed / 1000 = GWh.
    """
    n = len(pairs)
    if n == 0:
        return {
            "n": 0, "mae": None, "rmse": None, "bias": None, "nmae": None,
            "mape": None, "correlation": None, "meanActual": None,
            "meanForecast": None, "overForecastHours": 0, "underForecastHours": 0,
            "exactHours": 0, "cumulativeEnergyErrorGWh": 0.0,
        }
    errors = [f - a for f, a in pairs]
    actuals = [a for _, a in pairs]
    forecasts = [f for f, _ in pairs]
    mae = sum(abs(e) for e in errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    bias = sum(errors) / n
    mean_actual = sum(actuals) / n
    mean_forecast = sum(forecasts) / n
    ape = [abs(e) / a for e, (_, a) in zip(errors, pairs) if a != 0]
    mape = (sum(ape) / len(ape) * 100.0) if ape else None
    correlation = None
    if n > 1:
        mf, ma = mean_forecast, mean_actual
        num = sum((f - mf) * (a - ma) for f, a in pairs)
        den_f = sum((f - mf) ** 2 for f in forecasts)
        den_a = sum((a - ma) ** 2 for a in actuals)
        if den_f > 0 and den_a > 0:
            correlation = num / math.sqrt(den_f * den_a)
    return {
        "n": n,
        "mae": round(mae, 1),
        "rmse": round(rmse, 1),
        "bias": round(bias, 1),
        "nmae": round(mae / mean_actual, 4) if mean_actual else None,
        "mape": round(mape, 2) if mape is not None else None,
        "correlation": round(correlation, 4) if correlation is not None else None,
        "meanActual": round(mean_actual, 1),
        "meanForecast": round(mean_forecast, 1),
        "overForecastHours": sum(1 for e in errors if e > 0),
        "underForecastHours": sum(1 for e in errors if e < 0),
        "exactHours": sum(1 for e in errors if e == 0),
        "cumulativeEnergyErrorGWh": round(sum(errors) / 1000.0, 2),
    }


def build_day_series(actual_rows: list[dict], forecast_rows: list[dict],
                     delivery_date: date, cutoff: str = "09:50") -> dict:
    """Full hourly series + summaries for one delivery day."""
    hourly = {parse_ts(r["startTime"]): r["generation"] for r in hourly_actuals(actual_rows)}
    selections = select_decision_forecasts(forecast_rows, delivery_date, cutoff)
    deadline = decision_deadline(delivery_date, cutoff)
    hours = []
    decision_pairs: list[tuple[float, float]] = []
    leaky_pairs: list[tuple[float, float]] = []
    for sel in selections:
        start = sel["startTime"]
        actual = hourly.get(start)
        forecast = sel["forecast"]
        leaky = sel["leakyForecast"]
        error = (forecast - actual) if (forecast is not None and actual is not None) else None
        if forecast is not None and actual is not None:
            decision_pairs.append((forecast, actual))
        if leaky is not None and actual is not None:
            leaky_pairs.append((leaky, actual))
        hours.append(
            {
                "hour": start.isoformat().replace("+00:00", "Z"),
                "hourLabel": start.strftime("%H:00"),
                "actual": round(actual, 1) if actual is not None else None,
                "forecast": round(forecast, 1) if forecast is not None else None,
                "publishTime": sel["publishTime"].isoformat().replace("+00:00", "Z") if sel["publishTime"] else None,
                "leadHours": round(sel["leadHours"], 1) if sel["leadHours"] is not None else None,
                "error": round(error, 1) if error is not None else None,
                "errorPct": round(error / actual * 100.0, 1) if (error is not None and actual) else None,
                "leakyForecast": round(leaky, 1) if leaky is not None else None,
                "leakyPublishTime": sel["leakyPublishTime"].isoformat().replace("+00:00", "Z") if sel["leakyPublishTime"] else None,
                "leakyError": round(leaky - actual, 1) if (leaky is not None and actual is not None) else None,
            }
        )
    return {
        "date": delivery_date.isoformat(),
        "cutoff": cutoff,
        "deadline": deadline.isoformat().replace("+00:00", "Z"),
        "hours": hours,
        "summary": metrics(decision_pairs),
        "leakySummary": metrics(leaky_pairs),
    }


# Lead-time buckets: (label, min_hours_inclusive, max_hours_exclusive)
LEAD_BUCKETS = [
    ("0–12 h", 0.0, 12.0),
    ("12–18 h", 12.0, 18.0),
    ("18–24 h", 18.0, 24.0),
    ("24–30 h", 24.0, 30.0),
    ("30–38 h", 30.0, 38.01),
    ("38 h +", 38.01, float("inf")),
]


def lead_time_buckets(day_series_list: list[dict]) -> list[dict]:
    """Aggregate decision-forecast accuracy by forecast lead time."""
    bucket_pairs: dict[str, list[tuple[float, float]]] = {label: [] for label, _, _ in LEAD_BUCKETS}
    bucket_leads: dict[str, list[float]] = {label: [] for label, _, _ in LEAD_BUCKETS}
    for day in day_series_list:
        for h in day["hours"]:
            if h["forecast"] is None or h["actual"] is None or h["leadHours"] is None:
                continue
            for label, lo, hi in LEAD_BUCKETS:
                if lo <= h["leadHours"] < hi:
                    bucket_pairs[label].append((h["forecast"], h["actual"]))
                    bucket_leads[label].append(h["leadHours"])
                    break
    out = []
    for label, _, _ in LEAD_BUCKETS:
        m = metrics(bucket_pairs[label])
        leads = bucket_leads[label]
        out.append({
            "bucket": label,
            "n": m["n"], "mae": m["mae"], "rmse": m["rmse"], "bias": m["bias"],
            "meanLeadHours": round(sum(leads) / len(leads), 1) if leads else None,
        })
    return out


def summarise_period(actual_rows: list[dict], forecast_rows: list[dict],
                     dates: list[date], cutoff: str = "09:50") -> dict:
    """January overview: overall + daily + lead buckets + worst/best days."""
    day_series = [build_day_series(actual_rows, forecast_rows, d, cutoff) for d in dates]
    all_pairs: list[tuple[float, float]] = []
    all_leaky: list[tuple[float, float]] = []
    daily = []
    for day in day_series:
        for h in day["hours"]:
            if h["actual"] is not None and h["forecast"] is not None:
                all_pairs.append((h["forecast"], h["actual"]))
            if h["actual"] is not None and h["leakyForecast"] is not None:
                all_leaky.append((h["leakyForecast"], h["actual"]))
        s = day["summary"]
        daily.append({
            "date": day["date"], "mae": s["mae"], "rmse": s["rmse"],
            "bias": s["bias"], "meanActual": s["meanActual"], "n": s["n"],
            "correlation": s["correlation"],
        })
    ranked = sorted([d for d in daily if d["mae"] is not None], key=lambda d: d["mae"], reverse=True)
    return {
        "cutoff": cutoff,
        "period": {"from": dates[0].isoformat(), "to": dates[-1].isoformat(), "days": len(dates)},
        "overall": metrics(all_pairs),
        "leakyOverall": metrics(all_leaky),
        "daily": daily,
        "leadBuckets": lead_time_buckets(day_series),
        "worstDays": ranked[:5],
        "bestDays": list(reversed(ranked[-5:])) if ranked else [],
    }


def list_runs(forecast_rows: list[dict], delivery_date: date, cutoff: str = "09:50") -> dict:
    """All publish runs targeting a delivery day, with eligibility flags."""
    deadline = decision_deadline(delivery_date, cutoff)
    runs: dict[datetime, int] = defaultdict(int)
    for row in forecast_rows:
        start = parse_ts(row["startTime"])
        if start.date() == delivery_date:
            runs[parse_ts(row["publishTime"])] += 1
    selected = None
    eligible_times = [t for t in runs if t < deadline]
    if eligible_times:
        selected = max(eligible_times)
    run_list = [
        {
            "publishTime": t.isoformat().replace("+00:00", "Z"),
            "hoursCovered": runs[t],
            "eligible": t < deadline,
            "selected": selected is not None and t == selected,
        }
        for t in sorted(runs)
    ]
    return {
        "date": delivery_date.isoformat(),
        "cutoff": cutoff,
        "deadline": deadline.isoformat().replace("+00:00", "Z"),
        "selectedPublishTime": selected.isoformat().replace("+00:00", "Z") if selected else None,
        "runs": run_list,
    }
