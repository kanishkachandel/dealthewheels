"""Each test here is the automated twin of one button in the guided demo."""
from tests.test_fair_allocation import login  # noqa: F401  (imported first to pin the test database)

from fastapi.testclient import TestClient

from app.main import app


def admin_headers(client) -> dict:
    return {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}


def call(client, path: str, method: str = "POST") -> dict:
    response = client.request(method, path, headers=admin_headers(client))
    assert response.status_code == 200, response.text
    return response.json()


def counts(standings) -> dict:
    return {row["vendor_name"]: row["allocated_trips"] for row in standings["rows"]}


def test_ten_trips_land_on_the_promised_five_three_two_split():
    with TestClient(app) as client:
        body = call(client, "/api/demo/run-ten")
        assert counts(body["standings"]) == {"Vendor One": 5, "Vendor Two": 3, "Vendor Three": 2}
        # Nobody is left owed anything once the split divides exactly.
        assert all(abs(row["running_shortfall"]) < 1e-9 for row in body["standings"]["rows"])


def test_every_decision_is_explained_by_the_shortfall_trace():
    with TestClient(app) as client:
        body = call(client, "/api/demo/allocate-one")
        winner = [row for row in body["decision"] if row["winner"]]
        assert len(winner) == 1
        eligible = [row for row in body["decision"] if row["eligible"]]
        assert winner[0]["shortfall"] == max(row["shortfall"] for row in eligible)


def test_capacity_guard_skips_the_most_owed_vendor_when_it_has_no_cab():
    with TestClient(app) as client:
        call(client, "/api/demo/run-ten")
        body = call(client, "/api/demo/capacity-guard")
        blocked = body["blocked_row"]
        assert blocked["eligible"] is False and blocked["reason"] == "no free cab"
        # It was genuinely owed the most and was still passed over.
        assert blocked["shortfall"] >= max(row["shortfall"] for row in body["decision"] if row["eligible"])
        assert not any(row["winner"] for row in body["decision"] if row["vendor_id"] == blocked["vendor_id"])


def test_rejection_reallocates_and_cools_the_rejecting_vendor_off():
    with TestClient(app) as client:
        body = call(client, "/api/demo/rejection")
        assert body["rejected_vendor"] != body["reassigned_vendor"]
        assert body["audit_trail"] == ["ASSIGNED", "REJECTED", "REASSIGNED"]
        assert body["cooloff_until"]


def test_escort_trips_are_a_separate_stream_from_normal_trips():
    with TestClient(app) as client:
        call(client, "/api/demo/run-ten")
        normal_before = call(client, "/api/demo/report")["standings"]["total_trips"]
        body = call(client, "/api/demo/escort-stream")
        assert body["standings"]["total_trips"] == 5           # escort pool counted on its own
        assert body["normal_standings"]["total_trips"] == normal_before  # normal pool untouched


def test_replaying_the_same_day_produces_an_identical_split():
    with TestClient(app) as client:
        body = call(client, "/api/demo/determinism")
        assert body["identical"] is True
        assert body["hash_one"] == body["hash_two"]
        assert len(body["run_one"]) == 10


def test_yesterday_shortfall_is_repaid_today():
    with TestClient(app) as client:
        body = call(client, "/api/demo/carry-forward")
        owed = next(row for row in body["day_one"]["standings"]["rows"] if row["vendor_name"] == "Vendor Two")
        assert owed["allocated_trips"] == 0 and owed["running_shortfall"] > 0
        repaid = [step["vendor_name"] for step in body["day_two"]["steps"][:3]]
        assert repaid == ["Vendor Two"] * 3  # the starved vendor is served first the next day


def test_concurrent_requests_never_oversell_the_last_cabs():
    with TestClient(app) as client:
        body = call(client, "/api/demo/race?workers=12")
        assert body["assigned"] == body["free_cabs_before"]
        assert body["refused"] == body["workers"] - body["free_cabs_before"]
        assert body["no_vendor_oversold"] is True
        assert all(count >= 0 for count in body["remaining_cabs"].values())


def test_a_month_of_uneven_volume_converges_on_the_contract():
    with TestClient(app) as client:
        body = call(client, "/api/demo/convergence?days=30")
        assert body["total_trips"] > 5000
        assert body["worst_drift_percent"] < 0.05          # long-run shares hold
        assert all(abs(row["residue"]) < 1.0 for row in body["rows"])  # no slow drift of whole trips


def test_demo_endpoints_reject_an_unauthenticated_caller():
    with TestClient(app) as client:
        assert client.post("/api/demo/run-ten").status_code == 401
