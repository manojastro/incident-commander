"""Confidence rule tests for to_evidence()."""

from incident_commander import tools
from incident_commander.evidence import reset_evidence_counter, to_evidence


def setup_function(_: object) -> None:
    reset_evidence_counter()


def test_logs_error_at_incident_time_is_high() -> None:
    res = tools.get_logs("checkout-api", "INC001")
    ev = to_evidence("get_logs", res, context="checkout-api")
    assert ev.confidence == "HIGH"


def test_kedb_similarity_only_is_low() -> None:
    res = tools.search_kedb("latency", "INC002")
    # best hit sim 0.88 < 0.9 -> LOW
    ev = to_evidence("search_kedb", res, context="checkout-api")
    assert ev.confidence == "LOW"


def test_kedb_high_sim_is_medium_never_high() -> None:
    res = tools.search_kedb("pool", "INC001")  # sim 0.92
    ev = to_evidence("search_kedb", res, context="checkout-api")
    assert ev.confidence == "MEDIUM"


def test_change_within_window_is_medium() -> None:
    res = tools.list_recent_changes("checkout-api", "INC001")
    ev = to_evidence("list_recent_changes", res, context="checkout-api")
    assert ev.confidence == "MEDIUM"


def test_no_changes_is_low() -> None:
    res = tools.list_recent_changes("login-api", "INC005")
    ev = to_evidence("list_recent_changes", res, context="login-api")
    assert ev.confidence == "LOW"
    assert "no recent changes" in ev.summary


def test_tool_caps_respected() -> None:
    res = tools.get_logs("checkout-api", "INC001")
    assert len(res["lines"]) <= 20  # type: ignore[operator]
    res2 = tools.search_kedb("x", "INC002")
    assert len(res2["hits"]) <= 5  # type: ignore[operator]
