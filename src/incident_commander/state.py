"""Pydantic v2 state model for the Incident Commander graph."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
HypothesisStatus = Literal["open", "supported", "rejected"]
ApprovalDecision = Literal["pending", "approved", "rejected"]
RunStatus = Literal["running", "waiting_approval", "executing", "done", "escalated"]


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class Incident(BaseModel):
    number: str
    title: str
    description: str
    service: str
    opened_at: str
    status: str = "New"


class Triage(BaseModel):
    category: Literal["network", "database", "application", "unknown"] = "unknown"
    priority: Literal["P1", "P2", "P3", "P4"] = "P3"
    summary: str = ""


class Hypothesis(BaseModel):
    text: str
    status: HypothesisStatus = "open"


class Evidence(BaseModel):
    id: str
    source: str
    summary: str
    raw_ref: str = ""
    confidence: Confidence = "LOW"
    ts: str = Field(default_factory=utcnow_iso)


class Claim(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class RCA(BaseModel):
    root_cause: str = ""
    contributing_factors: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)


class ProposedAction(BaseModel):
    tool: str = "add_work_note"
    args: dict[str, str] = Field(default_factory=dict)
    rationale: str = ""


class Approval(BaseModel):
    status: ApprovalDecision = "pending"
    decided_by: str = ""
    comment: str = ""
    decided_at: str = ""


class Budget(BaseModel):
    steps: int = 0
    max_steps: int = 12
    tokens: int = 0
    usd: float = 0.0
    max_usd: float = 0.50
    started_at: str = Field(default_factory=utcnow_iso)
    timeout_s: float = 60.0


class RunState(BaseModel):
    run_id: str = ""
    incident: Incident
    triage: Triage = Field(default_factory=Triage)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    rca: RCA | None = None
    proposed_action: ProposedAction | None = None
    approval: Approval = Field(default_factory=Approval)
    action_result: str = ""
    verification: str = ""
    budget: Budget = Field(default_factory=Budget)
    errors: list[str] = Field(default_factory=list)
    status: RunStatus = "running"
    tool_history: list[str] = Field(default_factory=list)
    specialist_visits: dict[str, int] = Field(default_factory=dict)
    timeline: list[str] = Field(default_factory=list)

    def log(self, msg: str) -> None:
        self.timeline.append(f"[step {self.budget.steps}] {msg}")

    def evidence_ids(self) -> set[str]:
        return {e.id for e in self.evidence}
