"""FASTAPI service for the mobile churn model."""

import json
import os
import math 
import pandas as pd 

from pydantic import BaseModel, ConfigDict, Field
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
from fastapi import FastAPI, HTTPException
from churn.data import FEATURES, skapa_features

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

class Customer(BaseModel):
    """Input schema for a single customer prediction."""

    model_config = ConfigDict(extra="forbid")

    alder: int = Field(ge=18, le=100)
    region: str = Field(min_length=1)
    abonnemang: str = Field(min_length=1)
    manader_som_kund: int = Field(ge=0)
    manadskostnad: float = Field(ge=0, allow_inf_nan=False)
    data_gb_per_manad: float = Field(ge=0, allow_inf_nan=False)
    supportarenden_12m: int = Field(ge=0)

class Prediction(BaseModel):
    churn_probability: float = Field(ge=0, le=1)
    model_version: str

@app.post("/predict", response_model=Prediction)
def predict(customer: Customer):
    """ Predict churn probability using the trained model."""
    if getattr(app.state, "model", None) is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded",
            )

    # Convert validated input to a Dataframe. 
    df = pd.DataFrame([customer.model_dump()])

    # Reuse the exact feature engineering from training.
    features = skapa_features(df)[FEATURES]

    # Probability of class 1 (customer churn)
    probability = float(
        app.state.model.predict_proba(features)[0, 1]
    )

    if not math.isfinite(probability):
        raise HTTPException(
            status_code=500,
            detail="Model returned invalid probability",
        )

    return Prediction(
        churn_probability=probability,
        model_version=app.state.metadata.get("commit", "unknown"),
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
            "commit", "unkknown",
        ),
        "api_version": "2.0",
    }


@app.get("/model-info")
def model_info():
    if getattr(app.state, "model", None) is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded",
            )

    return app.state.metadata 