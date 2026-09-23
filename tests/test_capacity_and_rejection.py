from tests.test_fair_allocation import login
from fastapi.testclient import TestClient
from app.main import app


def test_capacity_exhaustion_returns_clean_domain_error():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        response = client.post("/api/trips", headers={"Authorization": f"Bearer {admin}"}, json={"distance_km": 100, "trip_type": "ESCORT", "idempotency_key": "no-escort-capacity"})
        assert response.status_code == 422
        assert response.json()["code"] == "NO_ELIGIBLE_VENDOR"
