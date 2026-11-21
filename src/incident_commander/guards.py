"""Hard guards in code: budget, timeout, loop breaker, allowlist."""

from __future__ import annotations

from datetime import UTC, datetime

from incident_commander.state import RCA, Evidence, RunState

ALLOWLIST = {"add_work_note", "update_incident_state", "restart_service", "rollback_change"}


def is_allowed_action(tool: str) -> bool:
    return tool in ALLOWLIST


def elapsed_s(state: RunState) -> float:
    try:
        started = datetime.fromisoformat(state.budget.started_at)
    except ValueError:
        return 0.0
    return (datetime.now(UTC) - started).total_seconds()


def guard_tripped(state: RunState) -> str:
    """Return reason string if any guard trips, else ''."""
    b = state.budget
    if b.steps >= b.max_steps:
        return f"max steps {b.max_steps} reached"
    if b.usd >= b.max_usd:
        return f"max USD {b.max_usd:.2f} reached"
    if elapsed_s(state) > b.timeout_s:
        return f"timeout {b.timeout_s}s exceeded"
    if detect_loop(state.tool_history):
        return "loop breaker: same tool called 3x in a row"
    return ""


def detect_loop(history: list[str]) -> bool:
    return len(history) >= 3 and history[-1] == history[-2] == history[-3]


Gap = str


def check_claims_grounded(rca: RCA, evidence: list[Evidence]) -> list[Gap]:
    """Code critic: every claim needs >=1 real evidence id; root cause must
    not rest on LOW-only evidence stated as certain. Returns gap strings."""
    gaps: list[str] = []
    known = {e.id: e for e in evidence}
    for i, claim in enumerate(rca.claims):
        if not claim.evidence_ids:
            gaps.append(f"claim {i} has no evidence ids: {claim.text[:80]}")
            continue
        for eid in claim.evidence_ids:
            if eid not in known:
                gaps.append(f"claim {i} cites unknown evidence {eid}")
    # Root-cause certainty check: find claims mentioning root cause with only LOW evidence.
    for i, claim in enumerate(rca.claims):
        if "root cause" in claim.text.lower() or i == 0 and rca.claims:
            linked = [known[e] for e in claim.evidence_ids if e in known]
            if linked and all(e.confidence == "LOW" for e in linked):
                gaps.append(f"claim {i} states root cause on LOW-only evidence")
    # RCA with zero claims is a gap.
    if not rca.claims:
        gaps.append("rca has no claims")
    return gaps
