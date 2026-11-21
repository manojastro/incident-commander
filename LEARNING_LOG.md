# LEARNING_LOG

## M-slice — Mock-first Incident Commander — 2026-09-18
**Built:** state graph (triage/planner/supervisor/3 specialists/critic/HITL/verify), stub MCP tools with caps, FastAPI + SSE + HTML, JSON restart-resume, baseline + 5x2 eval.
**New concepts:** state graph = major-incident bridge with defined roles; `route_next` = bridge manager routing; checkpointer = bridge notes anyone can resume.
**Learner tasks:** n/a (mock-first slice built agent-side; learner owns RCA rubric + DB prompt next).
**Break-it result:** predicted loop breaker at 3 repeats / actual 3; predicted red-herring avoided / actual avoided via network-first routing + critic.
**Quiz:** pending.
**Open questions:** LangGraph adapter version; Langfuse self-host vs cloud; model split; per-run budget.
**Interview line I can now say:** "My agent gathers evidence with confidence labels, grounds every RCA claim in code, and pauses for human approval before any write — and I measured it against a fixed workflow."
