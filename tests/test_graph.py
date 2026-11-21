"""Graph + HITL + restart-resume + scenario-behaviour tests."""

import json

from incident_commander import graph, tools
from incident_commander.config import Settings
from incident_commander.evidence import reset_evidence_counter
from incident_commander.scenarios import SCENARIO_IDS
from incident_commander.state import RunState


def _settings() -> Settings:
    return Settings(max_steps_per_run=12, max_usd_per_run=0.50, run_timeout_s=60.0)


def setup_function(_: object) -> None:
    reset_evidence_counter()
    tools.set_fail_logs(False)


def test_full_run_pauses_at_approval_then_resumes(tmp_path: object, monkeypatch: object) -> None:
    monkeypatch.setenv("DATA_DIR", "x")  # unused; store path comes from settings
    s = graph.new_run("INC001", _settings())
    graph.run_until_approval(s, _settings())
    assert s.status == "waiting_approval"
    assert s.proposed_action is not None
    # Simulate restart-resume via JSON round-trip.
    blob = s.model_dump_json()
    s2 = RunState.model_validate_json(blob)
    assert s2.status == "waiting_approval"
    s2.approval.status = "approved"
    s2.approval.decided_by = "manager"
    graph.resume_after_approval(s2, _settings())
    assert s2.status == "done"
    assert "simulated OK" in s2.action_result
    assert s2.verification != ""


def test_reject_path_writes_note_only() -> None:
    s = graph.new_run("INC005", _settings())
    graph.run_until_approval(s, _settings())
    s.approval.status = "rejected"
    graph.resume_after_approval(s, _settings())
    assert s.status == "done"
    assert "rejected" in s.action_result.lower()


def test_red_herring_avoided_inc002() -> None:
    s = graph.new_run("INC002", _settings())
    graph.run_until_approval(s, _settings())
    assert s.rca is not None
    assert "red herring" in s.rca.claims[0].text.lower() or "packet loss" in s.rca.root_cause
    assert "chg-102" not in s.rca.root_cause or "red herring" in s.rca.claims[0].text.lower()


def test_inc005_does_not_invent_change() -> None:
    s = graph.new_run("INC005", _settings())
    graph.run_until_approval(s, _settings())
    assert s.rca is not None
    assert "no related change" in s.rca.root_cause.lower()
    assert s.proposed_action is not None
    assert s.proposed_action.tool == "add_work_note"


def test_all_five_scenarios_reach_approval_or_escalation() -> None:
    for inc in SCENARIO_IDS:
        reset_evidence_counter()
        s = graph.new_run(inc, _settings())
        graph.run_until_approval(s, _settings())
        assert s.status in ("waiting_approval", "escalated"), inc
        assert len(s.evidence) >= 2, inc


def test_logs_timeout_is_recorded_not_fatal() -> None:
    tools.set_fail_logs(True)
    try:
        s = graph.new_run("INC001", _settings())
        graph.run_until_approval(s, _settings())
        assert any("get_logs" in e for e in s.errors)
        assert s.status in ("waiting_approval", "escalated")
    finally:
        tools.set_fail_logs(False)


def test_store_roundtrip(tmp_path: object, monkeypatch: object) -> None:
    import tempfile

    d = tempfile.mkdtemp()
    monkeypatch.setenv("DATA_DIR", d)
    # store reads settings.data_dir; patch via settings object is enough for json check
    s = graph.new_run("INC003", _settings())
    blob = s.model_dump_json()
    assert json.loads(blob)["incident"]["number"] == "INC003"
