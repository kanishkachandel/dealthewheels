import os
from datetime import date

os.environ["DATABASE_URL"] = "sqlite:///./test_dealthewheels.db"

from fastapi.testclient import TestClient
from app.main import app
from app.db.base import Base
from app.db.session import engine


def setup_module():
    Base.metadata.drop_all(engine)


def login(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    return response.json()["access_token"]


def test_most_owed_first_converges_deterministically():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {admin}"}
        zones = client.get("/api/zones", headers=headers).json()
        zone_id = zones[0]["id"]
        credentials_by_id = {}
        for name, share in (("Vendor One", 50), ("Vendor Two", 30), ("Vendor Three", 20)):
            response = client.post("/api/vendors", headers=headers, json={"name": name, "active_cab_count": 20, "username": name.replace(" ", "").lower(), "password": "vendor-pass", "shares": [{"zone_id": zone_id, "trip_type": "NORMAL", "target_percent": share}]})
            assert response.status_code == 201, response.text
            credentials_by_id[response.json()["id"]] = name.replace(" ", "").lower()
        assigned = []
        for index in range(10):
            response = client.post("/api/trips", headers=headers, json={"distance_km": 10, "trip_type": "NORMAL", "idempotency_key": f"trip-{index}"})
            assert response.status_code == 201, response.text
            assigned.append(response.json()["assigned_vendor_id"])
        assert len(set(assigned)) == 3
        # Same idempotency key must return precisely the original assignment.
        retried = client.post("/api/trips", headers=headers, json={"distance_km": 10, "trip_type": "NORMAL", "idempotency_key": "trip-0"})
        assert retried.status_code == 201
        assert retried.json()["assigned_vendor_id"] == assigned[0]
        # Rejecting vendor is cooled off and the offer moves to another eligible vendor.
        vendor_token = login(client, credentials_by_id[assigned[0]], "vendor-pass")
        rejected = client.post(f"/api/trips/{retried.json()['id']}/reject", headers={"Authorization": f"Bearer {vendor_token}"})
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["assigned_vendor_id"] != assigned[0]
        report = client.get(f"/api/reports/share?date={date.today().isoformat()}", headers=headers)
        assert report.status_code == 200
        assert report.json()["total_trips"] == 10
        monthly = client.get(f"/api/reports/share?month={date.today().strftime('%Y-%m')}", headers=headers)
        assert monthly.status_code == 200
        assert monthly.json()["total_trips"] == 10
