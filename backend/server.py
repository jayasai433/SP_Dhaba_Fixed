"""Entrypoint shim. Supervisor references `server:app`, we host the real FastAPI
app in `main.py`. Kept as a one-liner so there is exactly one source of truth."""
from main import app  # noqa: F401
