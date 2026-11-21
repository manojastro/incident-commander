# Design — Incident Commander (mock-first slice)

## Small state graph we built (this repo)

Nodes: `triage` (code) → `planner` → `supervisor: route_next`
→ `network | database | application` specialists → evidence append
→ `draft RCA` → `critic: check_claims_grounded` (code)
→ `propose action` (allowlist) → **HITL interrupt** (JSON persist)
→ `execute` (mock) → `verify` → `close`.

Router `route_next(state) -> network | database | application | draft_rca | escalate`
checks guards first (max steps, max USD, timeout, loop-breaker), then routes by
triage category to the least-visited specialist, then stops when evidence is
sufficient (≥1 HIGH + ≥1 MEDIUM) or 3 specialist visits are done.

## LangGraph mapping (production)

| This repo | LangGraph |
|---|---|
| `RunState` (Pydantic) | `StateGraph` state schema + reducers (evidence/timeline append) |
| `node_*` functions | `add_node(...)` entries |
| `route_next` | `add_conditional_edges(supervisor, route_next, {...})` |
| pause at `waiting_approval` + JSON file | `interrupt()` + Postgres checkpointer, resume via API |
| specialist tool subsets | subgraphs with scoped tool lists (least privilege) |
| mock stub tools | MCP tools via MCP adapter (same names) |
| `usd_per_step` mock cost | Langfuse token/cost callback per LLM call |

## Deterministic (code) vs LLM reasoning per scenario

| Scenario | Deterministic (code decides) | Needs LLM reasoning (mocked here) |
|---|---|---|
| INC001 DB pool | triage=database, allowlist, critic grounding | summarise pool-exhaustion timeline, RCA wording |
| INC002 red herring | route to network despite recent change; critic | judge packet-loss vs css deploy, explain herring |
| INC003 OOM | triage=application, propose rollback_change | link heap-limit change to crashloop narrative |
| INC004 missing index | propose rollback_change, verify slow query | explain migration→index→scan chain |
| INC005 no change | refuse to invent change; note-only action | state "no related change" honestly, suggest DNS watch |

Rule kept throughout: **code decides, LLM explains** (priority, routing,
allow/deny, grounding are code; summaries and RCA prose are LLM).
