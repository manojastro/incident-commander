"""FastAPI surface: runs, approval gate, SSE stream, minimal HTML page."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from incident_commander import graph
from incident_commander.baseline import run_baseline
from incident_commander.config import get_settings
from incident_commander.scenarios import SCENARIO_IDS
from incident_commander.store import list_runs, load_run, run_to_dict, save_run
from incident_commander.timeline import export_timeline

app = FastAPI(title="Incident Commander (mock-first, offline)")


class StartRun(BaseModel):
    incident_number: str
    mode: str = "agent"  # agent | workflow


class Decision(BaseModel):
    decided_by: str = "manager"
    comment: str = ""
    new_tool: str = ""
    new_args: dict[str, str] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs")
def start_run(body: StartRun) -> dict[str, object]:
    settings = get_settings()
    if body.incident_number not in SCENARIO_IDS:
        raise HTTPException(400, f"unknown incident; try one of {SCENARIO_IDS}")
    if body.mode == "workflow":
        state = run_baseline(body.incident_number, settings)
    else:
        state = graph.new_run(body.incident_number, settings)
        graph.run_until_approval(state, settings)
    save_run(state)
    export_timeline(state)
    return {"run_id": state.run_id, "status": state.status, "state": run_to_dict(state)}


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    try:
        state = load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(404, "run not found") from None
    return {"run_id": run_id, "status": state.status, "state": run_to_dict(state)}


@app.get("/runs")
def all_runs() -> dict[str, object]:
    return {"runs": list_runs()}


@app.get("/runs/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
    try:
        state = load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(404, "run not found") from None

    async def gen():  # type: ignore[no-untyped-def]
        for t in state.timeline:
            yield f"data: {json.dumps({'t': t})}\n\n"
            await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'status': state.status})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


def _apply_decision(run_id: str, approve: bool, body: Decision) -> dict[str, object]:
    settings = get_settings()
    try:
        state = load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(404, "run not found") from None
    if state.status != "waiting_approval":
        raise HTTPException(409, f"run is {state.status}, not waiting_approval")
    now = datetime.now(UTC).isoformat()
    if approve:
        state.approval.status = "approved"
        # Edits map to a new proposed action but must stay on the allowlist.
        if body.new_tool and state.proposed_action is not None:
            from incident_commander.guards import is_allowed_action

            if not is_allowed_action(body.new_tool):
                raise HTTPException(400, f"tool {body.new_tool} not on allowlist")
            state.proposed_action.tool = body.new_tool
            if body.new_args is not None:
                state.proposed_action.args = body.new_args
    else:
        state.approval.status = "rejected"
    state.approval.decided_by = body.decided_by
    state.approval.comment = body.comment
    state.approval.decided_at = now
    state.log(f"human {body.decided_by} {'approved' if approve else 'rejected'}: {body.comment}")
    graph.resume_after_approval(state, settings)
    save_run(state)
    export_timeline(state)
    return {"run_id": run_id, "status": state.status, "state": run_to_dict(state)}


@app.post("/runs/{run_id}/approve")
def approve(run_id: str, body: Decision) -> dict[str, object]:
    return _apply_decision(run_id, True, body)


@app.post("/runs/{run_id}/reject")
def reject(run_id: str, body: Decision) -> dict[str, object]:
    return _apply_decision(run_id, False, body)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html><html><head><meta charset=utf-8><title>Incident Commander</title>
<style>body{font-family:system-ui,sans-serif;max-width:760px;margin:2em auto;padding:0 1em}
pre{background:#f4f4f4;padding:1em;white-space:pre-wrap}</style></head><body>
<h1>Incident Commander <small>(mock-first, offline · synthetic Acme only)</small></h1>
<p>Start a run, watch the timeline, approve/reject with a comment.</p>
<label>Incident <select id=inc>
<option>INC001</option><option>INC002</option><option>INC003</option>
<option>INC004</option><option>INC005</option></select></label>
<button onclick="start()">Start run</button>
<pre id=out>idle</pre>
<label>Comment <input id=cmt value="looks good"></label>
<button onclick="decide(true)">Approve</button>
<button onclick="decide(false)">Reject</button>
<script>let run=null;
async function start(){const inc=document.getElementById('inc').value;
 const r=await fetch('/runs',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({incident_number:inc})});const j=await r.json();run=j.run_id;
 document.getElementById('out').textContent=JSON.stringify(j,null,2);}
async function decide(ok){if(!run)return alert('start a run first');
 const c=document.getElementById('cmt').value;
 const r=await fetch(`/runs/${run}/`+(ok?'approve':'reject'),{method:'POST',
 headers:{'Content-Type':'application/json'},
 body:JSON.stringify({decided_by:'manager',comment:c})});
 const j=await r.json();document.getElementById('out').textContent=JSON.stringify(j,null,2);}
</script></body></html>"""
