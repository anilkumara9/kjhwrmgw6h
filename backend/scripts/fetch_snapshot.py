#!/usr/bin/env python3
"""Fetch Jan 2026 Elexon data and write the bundled snapshot.

- Actuals: FUELHH stream for settlement dates 2026-01-01 .. 2026-01-31,
  filtered to fuelType == WIND (half-hourly rows only).
- Forecasts: WINDFOR stream for publish times 2025-12-30 .. 2026-02-01,
  keeping only rows targeting January 2026 delivery hours.

Output: backend/data/jan2026_snapshot.json
Run:  python scripts/fetch_snapshot.py   (from backend/, or anywhere)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import elexon  # noqa: E402


def main() -> None:
    print("Fetching FUELHH wind actuals (Jan 2026) ...")
    actuals = elexon.fetch_actuals()
    print(f"  actual half-hourly wind rows: {len(actuals)}")
    print("Fetching WINDFOR forecasts (published 2025-12-30 .. 2026-02-01) ...")
    forecasts = elexon.fetch_forecasts()
    print(f"  forecast rows targeting Jan 2026: {len(forecasts)}")
    snapshot = {
        "description": "Elexon BMRS snapshot: FUELHH WIND actuals (half-hourly) and WINDFOR forecasts for January 2026 delivery.",
        "actuals": [
            {
                "startTime": r["startTime"],
                "settlementDate": r.get("settlementDate"),
                "settlementPeriod": r.get("settlementPeriod"),
                "fuelType": "WIND",
                "generation": r["generation"],
            }
            for r in actuals
        ],
        "forecasts": [
            {
                "startTime": r["startTime"],
                "publishTime": r["publishTime"],
                "generation": r["generation"],
            }
            for r in forecasts
        ],
    }
    out = Path(__file__).resolve().parent.parent / "data" / "jan2026_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh)
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
