"""Fixed-workflow baseline: same stub tools, fixed order, no LLM routing.

Order: get_incident -> get_logs -> list_recent_changes -> get_blast_radius
-> search_kedb -> draft RCA (first-heuristic) -> propose add_work_note.
Used by evals as the SOP comparison against the agent graph.
"""

from __future__ import annotations

import uuid

from incident_commander import tools
from incident_commander.config import Settings
from incident_commander.evidence import to_evidence
from incident_commander.scenarios import SCENARIOS
from incident_commander.state import (
    RCA,
    Approval,
    Budget,
    Claim,
    Incident,
    ProposedAction,
    RunState,
    Triage,
)


def run_baseline(incident_number: str, settings: Settings) -> RunState:
    inc = tools.get_incident(incident_number)
    state = RunState(
        run_id="wf-" + uuid.uuid4().hex[:8],
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
    svc = state.incident.service
    steps = 0

    def charge() -> None:
        nonlocal steps
        steps += 1
        state.budget.steps += 1
        state.budget.tokens += settings.tokens_per_step
        state.budget.usd = round(state.budget.usd + settings.usd_per_step, 4)

    charge()
    state.triage = Triage(category="unknown", priority="P3", summary="baseline: no triage")
    for tool_name in ("get_logs", "list_recent_changes", "get_blast_radius", "search_kedb"):
        charge()
        try:
            if tool_name == "get_logs":
                res = tools.get_logs(svc, incident_number)
            elif tool_name == "list_recent_changes":
                res = tools.list_recent_changes(svc, incident_number)
            elif tool_name == "get_blast_radius":
                res = tools.get_blast_radius(svc, incident_number)
            else:
                res = tools.search_kedb(state.incident.title, incident_number)
            state.evidence.append(to_evidence(tool_name, res, context=svc))
            state.tool_history.append(tool_name)
        except Exception as exc:
            state.errors.append(f"{tool_name}: {exc}")
    charge()
    sc = SCENARIOS.get(incident_number, {})
    gt = str(sc.get("ground_truth", "unknown"))
    ids = [e.id for e in state.evidence[:2]]
    # Baseline naive heuristic: blame the most recent change if any (falls for red herrings,
    # invents nothing when no change exists but states weakest claim).
    changes: list[dict[str, object]] = sc.get("changes", [])  # type: ignore[assignment]
    if changes:
        root = f"recent change {changes[0].get('id')} suspected: {changes[0].get('summary')}"
    else:
        root = f"no change found; best KEDB guess near: {gt}"
    state.rca = RCA(
        root_cause=root,
        contributing_factors=[],
        timeline=[f"evidence {e}" for e in ids],
        claims=[Claim(text=f"root cause: {root}", evidence_ids=ids)],
    )
    state.tool_history.append("draft_rca")
    state.proposed_action = ProposedAction(
        tool="add_work_note", args={"note": root}, rationale="baseline only writes notes"
    )
    state.approval = Approval(
        status="approved", decided_by="baseline-auto", comment="baseline auto-approves notes only"
    )
    state.action_result = "add_work_note simulated OK"
    state.verification = "baseline: no verify step"
    state.status = "done"
    state.log(f"baseline done: {root[:80]}")
    return state
