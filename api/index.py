"""Vercel serverless entry point: re-exports the FastAPI app.

The backend code lives in backend/app; the bundled January 2026 snapshot
(backend/data/jan2026_snapshot.json, wired in via vercel.json includeFiles)
means the function works even without live Elexon access.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
