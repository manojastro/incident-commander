# DEMO (90 seconds) — scenario INC001 with approval

1. `uv sync --group dev` then `uv run uvicorn incident_commander.api:app --port 8000` (0:00).
2. Open `http://localhost:8000` — pick INC001, click Start run (0:10).
   Say: "Agent triaged checkout 500s as database, gathered logs, changes, blast radius, KEDB."
3. Show timeline: HIGH log evidence + MEDIUM change evidence (0:30).
4. Proposed action `restart_service(checkout-api)` is waiting — enter comment "approved, low risk" and click Approve (0:50).
5. Show `action_result: simulated OK` + verification "no new ERROR" (1:10).
6. Open `reports/runs/<id>.md` — the major-incident timeline export (1:20).
