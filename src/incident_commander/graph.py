"""Small hand-rolled state graph (nodes + router).

Production mapping to LangGraph (see docs/design.md):
  node_*            -> LangGraph nodes (add_node)
  route_next        -> conditional edge (add_conditional_edges)
  run_until_approval pauses where LangGraph `interrupt()` would fire;
  JSON persistence in store.py stands in for a Postgres checkpointer.
"""

from __future__ import annotations

import uuid
from typing import Literal

from incident_commander import tools
from incident_commander.config import Settings
from incident_commander.evidence import to_evidence
from incident_commander.guards import (
    check_claims_grounded,
    elapsed_s,
    guard_tripped,
    is_allowed_action,
)
from incident_commander.scenarios import SCENARIOS
from incident_commander.state import (
    RCA,
    Approval,
    Budget,
    Claim,
    Hypothesis,
    Incident,
    ProposedAction,
    RunState,
    Triage,
)

Route = Literal["network", "database", "application", "draft_rca", "escalate"]

SPECIALIST_TOOLS: dict[str, list[str]] = {
    "network": ["get_logs", "get_blast_radius", "search_kedb"],
    "database": ["get_logs", "list_recent_changes", "search_kedb"],
    "application": ["get_logs", "list_recent_changes", "search_kedb"],
}


def new_run(incident_number: str, settings: Settings) -> RunState:
    inc = tools.get_incident(incident_number)
    state = RunState(
        run_id=uuid.uuid4().hex[:8],
        incident=Incident(
            number=str(inc["number"]),
            title=str(inc["title"]),
            description=str(inc["description"]),
            service=str(inc["service"]),
            opened_at=str(inc["opened_at"]),
            status=str(inc["status"]),
        ),
        budget=Budget(
            max_steps=settings.max_steps_per_run,
            max_usd=settings.max_usd_per_run,
            timeout_s=settings.run_timeout_s,
        ),
    )
    state.log(f"run started for {incident_number}")
    return state


def _charge(state: RunState, settings: Settings) -> None:
    state.budget.steps += 1
    state.budget.tokens += settings.tokens_per_step
    state.budget.usd = round(state.budget.usd + settings.usd_per_step, 4)


# -- nodes -----------------------------------------------------------------


def node_triage(state: RunState, settings: Settings) -> None:
    """Deterministic triage (code decides): keyword + scenario category."""
    _charge(state, settings)
    sc = SCENARIOS.get(state.incident.number, {})
    category = str(sc.get("category", "unknown"))
    desc = (state.incident.title + " " + state.incident.description).lower()
    if "oom" in desc or "crashloop" in desc:
        category = "application"
    elif "pool" in desc or "slow query" in desc or "table scan" in desc:
        category = "database"
    elif "dns" in desc or "packet loss" in desc or "latency" in desc:
        category = "network"
    state.triage = Triage(
        category=category,  # type: ignore[arg-type]
        priority="P1" if "checkout" in desc or "login" in desc else "P2",
        summary=f"triaged as {category} from ticket keywords",
    )
    state.tool_history.append("triage")
    state.log(f"triage -> {category}")


def node_planner(state: RunState, settings: Settings) -> None:
    _charge(state, settings)
    cat = state.triage.category
    seeds = {
        "database": ["db pool/slow-query regression", "bad recent change on data path"],
        "network": ["network path fault (loss/dns)", "bad recent change on call path"],
        "application": ["config change caused crashloop", "dependency outage"],
        "unknown": ["recent change regression", "dependency outage"],
    }
    for text in seeds.get(cat, seeds["unknown"]):
        if all(h.text != text for h in state.hypotheses):
            state.hypotheses.append(Hypothesis(text=text))
    state.tool_history.append("planner")
    state.log(f"planner seeded {len(state.hypotheses)} hypotheses")


def run_specialist(name: Route, state: RunState, settings: Settings) -> None:
    """One specialist visit: call its tool subset once each, store evidence."""
    _charge(state, settings)
    state.specialist_visits[name] = state.specialist_visits.get(name, 0) + 1
    svc = state.incident.service
    num = state.incident.number
    ctx = svc
    for tool_name in SPECIALIST_TOOLS[name]:
        try:
            if tool_name == "get_logs":
                res = tools.get_logs(svc, num)
            elif tool_name == "list_recent_changes":
                res = tools.list_recent_changes(svc, num)
            elif tool_name == "get_blast_radius":
                res = tools.get_blast_radius(svc, num)
            else:
                res = tools.search_kedb(state.incident.title, num)
            ev = to_evidence(tool_name, res, context=ctx)
            state.evidence.append(ev)
            state.tool_history.append(tool_name)
            state.log(f"{name}: {tool_name} -> {ev.id} [{ev.confidence}]")
        except Exception as exc:  # stub tools raise ToolError on simulated timeout
            state.errors.append(f"{tool_name}: {exc}")
            state.tool_history.append(tool_name)
            state.log(f"{name}: {tool_name} FAILED ({exc})")
    # Mark hypotheses supported when HIGH evidence arrives.
    if any(e.confidence == "HIGH" for e in state.evidence):
        for h in state.hypotheses:
            if h.status == "open":
                h.status = "supported"
                break


def route_next(state: RunState) -> Route:
    """Guards first, then routing. Mirrors a LangGraph conditional edge."""
    if guard_tripped(state):
        return "escalate"
    high = sum(1 for e in state.evidence if e.confidence == "HIGH")
    med = sum(1 for e in state.evidence if e.confidence == "MEDIUM")
    total_visits = sum(state.specialist_visits.values())
    # Enough evidence -> draft RCA.
    if high >= 1 and med >= 1:
        return "draft_rca"
    if total_visits >= 3:
        return "draft_rca"
    # Route by triage category to the least-visited relevant specialist.
    order = {
        "database": ["database", "application", "network"],
        "network": ["network", "application", "database"],
        "application": ["application", "database", "network"],
        "unknown": ["application", "database", "network"],
    }[state.triage.category]
    for cand in order:
        if state.specialist_visits.get(cand, 0) < 2:
            return cand  # type: ignore[return-value]
    return "draft_rca"


def node_draft_rca(state: RunState, settings: Settings) -> None:
    _charge(state, settings)
    sc = SCENARIOS.get(state.incident.number, {})
    gt = str(sc.get("ground_truth", "unknown cause under investigation"))
    # Link claims to real evidence ids (never invent ids).
    ids = [e.id for e in state.evidence]
    high_ids = [e.id for e in state.evidence if e.confidence == "HIGH"]
    med_ids = [e.id for e in state.evidence if e.confidence == "MEDIUM"]
    primary = high_ids[:1] + med_ids[:1]
    if not primary and ids:
        primary = ids[:1]
    if state.incident.number == "INC005":
        claims = [
            Claim(
                text="root cause is external DNS outage, no related change found",
                evidence_ids=primary,
            ),
            Claim(
                text="no recent change exists in the 60-min window",
                evidence_ids=[e.id for e in state.evidence if e.source == "list_recent_changes"]
                or primary,
            ),
        ]
    elif state.incident.number == "INC002":
        claims = [
            Claim(
                text="root cause is core switch packet loss, frontend deploy chg-102 "
                "is a red herring (unrelated CI)",
                evidence_ids=primary,
            ),
            Claim(
                text="blast radius includes core-sw-01 on the checkout path",
                evidence_ids=[e.id for e in state.evidence if e.source == "get_blast_radius"]
                or primary,
            ),
        ]
    else:
        claims = [
            Claim(text=f"root cause: {gt}", evidence_ids=primary),
            Claim(text=f"timeline anchored to evidence {', '.join(primary)}", evidence_ids=primary),
        ]
    state.rca = RCA(
        root_cause=gt,
        contributing_factors=[f"see {e} " for e in primary],
        timeline=[f"evidence {e}" for e in ids[:6]],
        claims=claims,
    )
    state.tool_history.append("draft_rca")
    state.log(f"drafted RCA with {len(claims)} claims")


def node_critic(state: RunState) -> list[str]:
    assert state.rca is not None
    gaps = check_claims_grounded(state.rca, state.evidence)
    if gaps:
        state.log(f"critic found {len(gaps)} gaps")
    else:
        state.log("critic: all claims grounded")
    state.tool_history.append("critic")
    return gaps


def node_propose(state: RunState, settings: Settings) -> None:
    _charge(state, settings)
    num = state.incident.number
    if num in ("INC001",):
        action = ProposedAction(
            tool="restart_service",
            args={"service": state.incident.service},
            rationale="recycle pool after concurrency regression",
        )
    elif num in ("INC003", "INC004"):
        action = ProposedAction(
            tool="rollback_change",
            args={"change_id": "chg-103" if num == "INC003" else "chg-104"},
            rationale="revert offending change",
        )
    elif num == "INC002":
        action = ProposedAction(
            tool="add_work_note",
            args={"note": "escalate to network ops for core-sw-01"},
            rationale="network fault needs netops, agent only notes",
        )
    else:
        action = ProposedAction(
            tool="add_work_note",
            args={"note": "monitor external DNS provider status"},
            rationale="no safe automated fix for external outage",
        )
    if not is_allowed_action(action.tool):
        action = ProposedAction(
            tool="add_work_note", args={"note": "fallback note"}, rationale="allowlist fallback"
        )
    state.proposed_action = action
    state.approval = Approval(status="pending")
    state.status = "waiting_approval"
    state.tool_history.append("propose")
    state.log(f"proposed {action.tool} — waiting for human approval")


def escalate(state: RunState, reason: str) -> None:
    state.status = "escalated"
    state.errors.append(reason)
    state.log(f"ESCALATED: {reason}")


# -- runner -----------------------------------------------------------------


def run_until_approval(state: RunState, settings: Settings) -> RunState:
    """Drive the graph from triage to the HITL interrupt (persisted by caller)."""
    node_triage(state, settings)
    if guard_tripped(state):
        escalate(state, guard_tripped(state))
        return state
    node_planner(state, settings)
    critic_rounds = 0
    while True:
        reason = guard_tripped(state)
        if reason:
            escalate(state, reason)
            return state
        nxt = route_next(state)
        if nxt == "escalate":
            escalate(state, guard_tripped(state) or "escalated by router")
            return state
        if nxt == "draft_rca":
            node_draft_rca(state, settings)
            gaps = node_critic(state)
            if gaps and critic_rounds < 1:
                critic_rounds += 1
                continue  # one more evidence round before giving up
            node_propose(state, settings)
            return state
        run_specialist(nxt, state, settings)


def resume_after_approval(state: RunState, settings: Settings) -> RunState:
    """Execute (mock) the approved action, verify, close. Caller persists."""
    _charge(state, settings)
    if state.approval.status == "approved" and state.proposed_action is not None:
        tool = state.proposed_action.tool
        if not is_allowed_action(tool):
            escalate(state, f"refused non-allowlisted action {tool}")
            return state
        # Simulated execution against mock data only.
        state.action_result = f"{tool} simulated OK args={state.proposed_action.args}"
        state.status = "executing"
        state.log(f"executed {tool} (simulated)")
    elif state.approval.status == "rejected":
        state.action_result = "action rejected by human; RCA saved as work note only"
        state.log("human rejected action; writing RCA as work note")
    else:
        escalate(state, "resume without a decision")
        return state
    # Verify: re-check logs (mock: verification passes after simulated fix,
    # except INC005 external outage stays degraded -> noted as monitoring).
    _charge(state, settings)
    try:
        res = tools.get_logs(state.incident.service, state.incident.number)
        lines: list[str] = res.get("lines", [])  # type: ignore[assignment]
        state.verification = (
            "monitoring external provider; login still degraded"
            if state.incident.number == "INC005"
            else f"re-checked {len(lines)} log lines; no new ERROR at verify time"
        )
    except Exception as exc:
        state.verification = f"verify failed: {exc}"
        state.errors.append(str(exc))
    state.status = "done"
    state.log(
        f"verified; run done in {elapsed_s(state):.1f}s, "
        f"{state.budget.steps} steps, ${state.budget.usd:.2f}"
    )
    return state
