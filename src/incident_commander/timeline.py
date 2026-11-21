"""Major-incident timeline export: reports/runs/<id>.md."""

from __future__ import annotations

from pathlib import Path

from incident_commander.config import get_settings
from incident_commander.state import RunState


def export_timeline(state: RunState) -> Path:
    d = Path(get_settings().reports_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{state.run_id}.md"
    ev_lines = (
        "\n".join(f"- {e.id} [{e.confidence}] ({e.source}): {e.summary}" for e in state.evidence)
        or "- none"
    )
    claims = (
        "\n".join(
            f"- {c.text} (evidence: {', '.join(c.evidence_ids) or 'none'})"
            for c in (state.rca.claims if state.rca else [])
        )
        or "- none"
    )
    tl = "\n".join(f"- {t}" for t in state.timeline) or "- none"
    p.write_text(
        f"# Incident timeline — {state.incident.number} (run {state.run_id})\n\n"
        f"**Synthetic data (Acme Retail Ltd).** Status: {state.status}\n\n"
        f"## Incident\n- {state.incident.title}\n- {state.incident.description}\n\n"
        f"## Triage\n- {state.triage.category} / {state.triage.priority}: "
        f"{state.triage.summary}\n\n"
        f"## Evidence\n{ev_lines}\n\n"
        f"## RCA\n- root cause: {state.rca.root_cause if state.rca else 'n/a'}\n\n"
        f"### Claims\n{claims}\n\n"
        f"## Action\n- proposed: {state.proposed_action.tool if state.proposed_action else 'n/a'} "
        f"{state.proposed_action.args if state.proposed_action else ''}\n"
        f"- approval: {state.approval.status} by {state.approval.decided_by or '-'} "
        f"({state.approval.comment or '-'})\n"
        f"- result: {state.action_result or '-'}\n"
        f"- verification: {state.verification or '-'}\n\n"
        f"## Budget\n- steps {state.budget.steps}/{state.budget.max_steps}, "
        f"tokens {state.budget.tokens}, usd ${state.budget.usd:.2f}/${state.budget.max_usd:.2f}\n\n"
        f"## Timeline\n{tl}\n\n"
        f"## Errors\n" + ("\n".join(f"- {e}" for e in state.errors) or "- none") + "\n",
        encoding="utf-8",
    )
    return p
