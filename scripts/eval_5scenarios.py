"""Eval: 5 scenarios x 2 runs, agent graph vs fixed-workflow baseline.

Writes reports/eval_agent_vs_workflow.json. All mock/offline.
Scoring rubric (mock ground truth in scenarios.py):
- rca_correct: ground-truth keywords in agent root_cause (+ red-herring rule).
- evidence_coverage: distinct tool sources collected / 4.
- red_herring_avoided (INC002): root cause must NOT blame chg-102 as cause.
- no_invented_change (INC005): must state no related change.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

from incident_commander.baseline import run_baseline  # noqa: E402
from incident_commander.config import Settings  # noqa: E402
from incident_commander.evidence import reset_evidence_counter  # noqa: E402
from incident_commander.graph import (  # noqa: E402
    new_run,
    resume_after_approval,
    run_until_approval,
)
from incident_commander.scenarios import SCENARIO_IDS  # noqa: E402

KEYWORDS: dict[str, list[str]] = {
    "INC001": ["pool"],
    "INC002": ["packet loss"],
    "INC003": ["oom", "heap"],
    "INC004": ["index"],
    "INC005": ["dns", "no related change"],
}


def score_rca(incident: str, root_cause: str, claims: list[str]) -> tuple[bool, bool]:
    kw = KEYWORDS[incident]
    rc = root_cause.lower()
    correct = all(k in rc for k in kw)
    joined = " ".join(claims).lower()
    red_avoided = True
    if incident == "INC002":
        # Blaming the css deploy as THE cause = fell for the herring.
        red_avoided = "red herring" in joined or "chg-102" not in rc
        correct = correct and red_avoided
    return correct, red_avoided


def run_agent(incident: str, s: Settings) -> dict[str, object]:
    reset_evidence_counter()
    t0 = time.perf_counter()
    state = new_run(incident, s)
    run_until_approval(state, s)
    # Auto-approve in eval (human simulated).
    if state.status == "waiting_approval":
        state.approval.status = "approved"
        state.approval.decided_by = "eval-auto"
        state.approval.comment = "auto-approve in offline eval"
        resume_after_approval(state, s)
    dt = time.perf_counter() - t0
    claims = [c.text for c in state.rca.claims] if state.rca else []
    correct, red = score_rca(incident, state.rca.root_cause if state.rca else "", claims)
    sources = {e.source for e in state.evidence}
    return {
        "mode": "agent",
        "incident": incident,
        "status": state.status,
        "rca_correct": correct,
        "red_herring_avoided": red,
        "evidence_coverage": round(len(sources) / 4, 2),
        "n_evidence": len(state.evidence),
        "steps": state.budget.steps,
        "tool_calls": len(
            [
                t
                for t in state.tool_history
                if t not in ("triage", "planner", "draft_rca", "critic", "propose")
            ]
        ),
        "tokens": state.budget.tokens,
        "usd": state.budget.usd,
        "time_s": round(dt, 3),
        "approvals_requested": 1,
    }


def run_wf(incident: str, s: Settings) -> dict[str, object]:
    reset_evidence_counter()
    t0 = time.perf_counter()
    state = run_baseline(incident, s)
    dt = time.perf_counter() - t0
    claims = [c.text for c in state.rca.claims] if state.rca else []
    correct, red = score_rca(incident, state.rca.root_cause if state.rca else "", claims)
    sources = {e.source for e in state.evidence}
    return {
        "mode": "workflow",
        "incident": incident,
        "status": state.status,
        "rca_correct": correct,
        "red_herring_avoided": red,
        "evidence_coverage": round(len(sources) / 4, 2),
        "n_evidence": len(state.evidence),
        "steps": state.budget.steps,
        "tool_calls": 4,
        "tokens": state.budget.tokens,
        "usd": state.budget.usd,
        "time_s": round(dt, 3),
        "approvals_requested": 0,
    }


def main() -> None:
    s = Settings()
    rows: list[dict[str, object]] = []
    for _rep in range(2):
        for inc in SCENARIO_IDS:
            rows.append(run_agent(inc, s))
            rows.append(run_wf(inc, s))
    out = Path("reports/eval_agent_vs_workflow.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    def agg(mode: str) -> dict[str, object]:
        sub = [r for r in rows if r["mode"] == mode]
        n = len(sub)
        return {
            "runs": n,
            "rca_accuracy": round(sum(1 for r in sub if r["rca_correct"]) / n, 2),
            "red_herring_avoided": round(sum(1 for r in sub if r["red_herring_avoided"]) / n, 2),
            "avg_evidence_coverage": round(sum(float(r["evidence_coverage"]) for r in sub) / n, 2),
            "avg_steps": round(sum(int(r["steps"]) for r in sub) / n, 2),
            "avg_usd": round(sum(float(r["usd"]) for r in sub) / n, 4),
            "avg_time_s": round(sum(float(r["time_s"]) for r in sub) / n, 3),
        }

    summary = {
        "agent": agg("agent"),
        "workflow": agg("workflow"),
        "scenarios": list(SCENARIO_IDS),
        "note": "synthetic Acme data, mock LLM costs, offline",
    }
    out.write_text(json.dumps({"rows": rows, "summary": summary}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
