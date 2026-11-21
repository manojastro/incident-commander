"""API + baseline tests (offline, no network)."""

from fastapi.testclient import TestClient

from incident_commander import api
from incident_commander.baseline import run_baseline
from incident_commander.config import Settings
from incident_commander.evidence import reset_evidence_counter

client = TestClient(api.app)


def _settings() -> Settings:
    return Settings()


def setup_function(_: object) -> None:
    reset_evidence_counter()


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_start_approve_flow() -> None:
    r = client.post("/runs", json={"incident_number": "INC003"})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    assert r.json()["status"] == "waiting_approval"
    a = client.post(f"/runs/{run_id}/approve", json={"decided_by": "manager", "comment": "go"})
    assert a.status_code == 200, a.text
    assert a.json()["status"] == "done"


def test_reject_flow() -> None:
    r = client.post("/runs", json={"incident_number": "INC004"})
    run_id = r.json()["run_id"]
    rej = client.post(
        f"/runs/{run_id}/reject", json={"decided_by": "manager", "comment": "not yet"}
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "done"


def test_approve_twice_is_409() -> None:
    r = client.post("/runs", json={"incident_number": "INC001"})
    run_id = r.json()["run_id"]
    client.post(f"/runs/{run_id}/approve", json={"decided_by": "m", "comment": "ok"})
    second = client.post(f"/runs/{run_id}/approve", json={"decided_by": "m", "comment": "again"})
    assert second.status_code == 409


def test_non_allowlisted_edit_rejected() -> None:
    r = client.post("/runs", json={"incident_number": "INC001"})
    run_id = r.json()["run_id"]
    bad = client.post(
        f"/runs/{run_id}/approve",
        json={"decided_by": "m", "comment": "x", "new_tool": "delete_database"},
    )
    assert bad.status_code == 400


def test_baseline_runs() -> None:
    s = run_baseline("INC001", _settings())
    assert s.status == "done"
    assert s.rca is not None
    assert len(s.evidence) == 4
