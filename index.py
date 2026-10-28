"""Vercel entry point: exposes the FastAPI app that lives in backend/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
