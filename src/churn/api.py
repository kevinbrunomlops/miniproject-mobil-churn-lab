"""FASTAPI service for the mobile churn model."""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
from fastapi import FastAPI, HTTPException

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "outputs"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the approved model and its metadata."""
    model_path = MODEL_DIR / "modell.joblib"
    metadata_path = MODEL_DIR / "matvarden.json"

    app.state.model = joblib.load(model_path)
    app.state.metadata = json.loads(
        metadata_path.read_text(encoding="utf-8")
    )

    yield

    app.state.model = None
    app.state.metadata = None

app = FastAPI(
    title="Mobil churn API",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/health")
def health():
    if getattr(app.state, "model", None) is None:
        raise HTTPException(
            status_code=503, 
            detail="Model not loaded",
            )

    return {
        "status": "ok",
        "model_version": app.state.metadata.get(
            "commit", "unkknown"
        ),
    }

@app.get("/model-info")
def model_info():
    if getattr(app.state, "model", None) is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded",
            )

    return app.state.metadata 