"""Vercel Python Serverless Function entrypoint for the Moneyball EPL FastAPI backend."""
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api import app  # noqa: E402, F401

