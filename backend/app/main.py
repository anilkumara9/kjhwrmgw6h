"""FastAPI app: day-ahead wind forecast explorer + accuracy evaluation."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import analysis, elexon

app = FastAPI(
    title="Day-Ahead Wind Forecast — Decision & Accuracy",
    description="Point-in-time wind forecast evaluation using only Elexon BMRS data (FUELHH + WINDFOR).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cache: dict | None = None


def get_data() -> dict:
    global _cache
    if _cache is None:
        _cache = elexon.load_data()
    return _cache


def jan_dates() -> list[date]:
    return [date(2026, 1, 1) + timedelta(days=i) for i in range(31)]


def validate_cutoff(cutoff: str) -> str:
    try:
        analysis.parse_cutoff(cutoff)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return cutoff


def parse_day(raw: str) -> date:
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Date must be YYYY-MM-DD") from exc
    if not (date(2026, 1, 1) <= parsed <= date(2026, 1, 31)):
        raise HTTPException(status_code=422, detail="Date must be within January 2026 (2026-01-01 .. 2026-01-31)")
    return parsed


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "reint-wind-forecast-backend"}


@app.get("/api/day/{day}")
def day_view(day: str, cutoff: str = Query("09:50")):
    validate_cutoff(cutoff)
    delivery = parse_day(day)
    data = get_data()
    result = analysis.build_day_series(data["actuals"], data["forecasts"], delivery, cutoff)
    result["dataSource"] = data.get("source")
    return result


@app.get("/api/summary")
def summary(cutoff: str = Query("09:50")):
    validate_cutoff(cutoff)
    data = get_data()
    result = analysis.summarise_period(data["actuals"], data["forecasts"], jan_dates(), cutoff)
    result["dataSource"] = data.get("source")
    return result


@app.get("/api/runs/{day}")
def runs_view(day: str, cutoff: str = Query("09:50")):
    validate_cutoff(cutoff)
    delivery = parse_day(day)
    data = get_data()
    result = analysis.list_runs(data["forecasts"], delivery, cutoff)
    result["dataSource"] = data.get("source")
    return result
