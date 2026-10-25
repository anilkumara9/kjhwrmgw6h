"""Elexon BMRS client with disk cache and bundled-snapshot fallback.

Only two datasets are used, exactly as specified in the brief:
- FUELHH  (actual half-hourly generation, filtered to fuelType == WIND)
- WINDFOR (hourly wind forecasts with publishTime)
"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta
from pathlib import Path

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache"
SNAPSHOT_PATH = DATA_DIR / "jan2026_snapshot.json"

JAN_START = date(2026, 1, 1)
JAN_END = date(2026, 1, 31)
FORECAST_PUBLISH_FROM = "2025-12-30T00:00:00Z"
FORECAST_PUBLISH_TO = "2026-02-01T00:00:00Z"


def _make_client():
    """Build an httpx client.

    Some sandboxes export a NO_PROXY list with bracketed IPv6 entries that
    httpx cannot parse; in that case pass the egress proxy explicitly with
    trust_env disabled instead of failing outright.
    """
    import os
    import ssl

    import httpx

    # Use the OS trust store (respects SSL_CERT_FILE) rather than certifi's
    # bundle, so corporate/egress proxies with locally-installed CAs verify.
    verify = ssl.create_default_context()
    proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    if proxy:
        try:
            return httpx.Client(timeout=120.0, verify=verify)
        except Exception:  # noqa: BLE001 - fall back to explicit proxy
            return httpx.Client(timeout=120.0, proxy=proxy, trust_env=False, verify=verify)
    return httpx.Client(timeout=120.0, verify=verify)


def _fetch_json(url: str, retries: int = 3) -> list:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with _make_client() as client:
                resp = client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else data.get("data", [])
        except Exception as exc:  # noqa: BLE001 - retried, then surfaced
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Elexon fetch failed: {url}") from last_error


def fetch_actuals() -> list[dict]:
    """Live FUELHH wind rows for Jan 2026 (half-hourly)."""
    url = (
        f"{BASE_URL}/datasets/FUELHH/stream"
        f"?settlementDateFrom={JAN_START.isoformat()}&settlementDateTo={JAN_END.isoformat()}&format=json"
    )
    rows = _fetch_json(url)
    return [r for r in rows if r.get("fuelType") == "WIND"]


def fetch_forecasts() -> list[dict]:
    """Live WINDFOR rows published 2025-12-30 .. 2026-02-01, chunked by 4 days."""
    rows: list[dict] = []
    start = date(2025, 12, 30)
    end = date(2026, 2, 1)
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=4), end)
        url = (
            f"{BASE_URL}/datasets/WINDFOR/stream"
            f"?publishDateTimeFrom={cursor.isoformat()}T00:00:00Z"
            f"&publishDateTimeTo={chunk_end.isoformat()}T00:00:00Z&format=json"
        )
        rows.extend(_fetch_json(url))
        cursor = chunk_end
    # Keep only forecasts targeting January 2026 delivery hours.
    return [r for r in rows if str(r.get("startTime", ""))[:10] >= "2026-01-01"
            and str(r.get("startTime", ""))[:10] <= "2026-01-31"]


def load_snapshot() -> dict | None:
    # Candidate locations: alongside the backend (local/Docker) and at the
    # repo root's backend/ folder (Vercel serverless layout via api/index.py).
    candidates = [
        SNAPSHOT_PATH,
        Path(__file__).resolve().parents[2] / "backend" / "data" / "jan2026_snapshot.json",
        Path.cwd() / "backend" / "data" / "jan2026_snapshot.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            with open(candidate, encoding="utf-8") as fh:
                return json.load(fh)
    return None


def load_data(force_live: bool = False) -> dict:
    """Load {actuals, forecasts, source}. Prefers live (cached), falls back to snapshot."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "jan2026_live.json"
    if not force_live and cache_file.exists():
        with open(cache_file, encoding="utf-8") as fh:
            cached = json.load(fh)
            cached["source"] = "disk-cache (live Elexon fetch)"
            return cached
    if not force_live:
        snapshot = load_snapshot()
        if snapshot is not None:
            return {
                "actuals": snapshot["actuals"],
                "forecasts": snapshot["forecasts"],
                "source": "bundled snapshot (backend/data/jan2026_snapshot.json)",
            }
    try:
        actuals = fetch_actuals()
        forecasts = fetch_forecasts()
        payload = {"actuals": actuals, "forecasts": forecasts}
        with open(cache_file, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return {**payload, "source": "live Elexon BMRS API"}
    except Exception:
        snapshot = load_snapshot()
        if snapshot is not None:
            return {
                "actuals": snapshot["actuals"],
                "forecasts": snapshot["forecasts"],
                "source": "bundled snapshot (live fetch failed)",
            }
        raise
