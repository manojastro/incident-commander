"""Guards + critic + router tests."""

from incident_commander import graph
from incident_commander.config import Settings
from incident_commander.evidence import reset_evidence_counter
from incident_commander.guards import (
    check_claims_grounded,
    detect_loop,
    is_allowed_action,
)
from incident_commander.state import RCA, Claim, Evidence


def _settings(**kw: object) -> Settings:
    return Settings(
        max_steps_per_run=int(kw.get("max_steps", 12)),
        max_usd_per_run=float(kw.get("max_usd", 0.50)),
        run_timeout_s=float(kw.get("timeout", 60.0)),
    )


def test_allowlist() -> None:
    assert is_allowed_action("restart_service")
    assert is_allowed_action("rollback_change")
    assert is_allowed_action("add_work_note")
    assert is_allowed_action("update_incident_state")
    assert not is_allowed_action("delete_database")
    assert not is_allowed_action("ssh_exec")


def test_loop_breaker_fires_after_same_tool_x3() -> None:
    assert not detect_loop(["get_logs", "get_logs"])
    assert detect_loop(["get_logs", "get_logs", "get_logs"])
    s = graph.new_run("INC001", _settings())
    s.tool_history = ["get_logs", "get_logs", "get_logs"]
    assert graph.route_next(s) == "escalate"


def test_max_steps_guard() -> None:
    s = graph.new_run("INC001", _settings(max_steps=2))
    s.budget.steps = 2
    assert graph.route_next(s) == "escalate"


def test_max_usd_guard() -> None:
    s = graph.new_run("INC001", _settings())
    s.budget.usd = 99.0
    assert graph.route_next(s) == "escalate"


def test_timeout_guard() -> None:
    s = graph.new_run("INC001", _settings(timeout=0.0001))
    import time

    time.sleep(0.01)
    assert graph.route_next(s) == "escalate"


def test_critic_flags_ungrounded_claim() -> None:
    ev = Evidence(id="EV-001-x", source="get_logs", summary="err", confidence="HIGH")
    rca = RCA(root_cause="x", claims=[Claim(text="root cause is x", evidence_ids=["EV-999"])])
    gaps = check_claims_grounded(rca, [ev])
    assert any("unknown evidence" in g for g in gaps)


def test_critic_flags_low_only_root_cause() -> None:
    ev = Evidence(id="EV-001-x", source="search_kedb", summary="hint", confidence="LOW")
    rca = RCA(
        root_cause="x", claims=[Claim(text="root cause is x for sure", evidence_ids=["EV-001-x"])]
    )
    gaps = check_claims_grounded(rca, [ev])
    assert any("LOW-only" in g for g in gaps)


def test_critic_passes_grounded() -> None:
    reset_evidence_counter()
    from incident_commander import tools
    from incident_commander.evidence import to_evidence

    res = tools.get_logs("checkout-api", "INC001")
    ev = to_evidence("get_logs", res, context="checkout-api")
    rca = RCA(
        root_cause="db pool", claims=[Claim(text="root cause: db pool", evidence_ids=[ev.id])]
    )
    assert check_claims_grounded(rca, [ev]) == []
