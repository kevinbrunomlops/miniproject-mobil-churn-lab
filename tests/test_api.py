"""Tests for the churn prediction API."""

import pytest 
from fastapi.testclient import TestClient

from churn.api import app

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def valid_customer():
    return {
        "alder": 75,
        "region": "Väst",
        "abonnemang": "Bas",
        "manader_som_kund": 103,
        "manadskostnad": 123.77,
        "data_gb_per_manad": 8.1,
        "supportarenden_12m": 2
    }

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "model_version" in response.json()

def test_model_info(client):
    response = client.get("/model-info")

    assert response.status_code == 200
    assert "roc_auc" in response.json()
    assert "data_sha256" in response.json()

def test_predict_valid_customer(client, valid_customer):
    response = client.post("/predict", json=valid_customer)

    assert response.status_code == 200

    result = response.json()
    assert 0 <= result["churn_probability"] <= 1
    assert "model_version" in result

def test_predict_invalid_age(client, valid_customer):
    valid_customer["alder"] = -5  # Invalid age

    response = client.post("/predict", json=valid_customer)

    assert response.status_code == 422

def test_predict_missing_field(client, valid_customer):
    del valid_customer["region"]  # Remove a required field

    response = client.post("/predict", json=valid_customer)

    assert response.status_code == 422

def test_predict_negative_cost(client, valid_customer):
    valid_customer["manadskostnad"] = -100.0  # Invalid negative cost

    response = client.post("/predict", json=valid_customer)

    assert response.status_code == 422