# ADR-001 — Hand-rolled graph instead of LangGraph for the mock-first slice

Status: accepted. Date: 2026-09-18.

Context: offline slice, no real LLM keys, must run with uv + pytest only.

Decision: implement nodes + `route_next` as plain functions over a Pydantic
state object; document the exact LangGraph mapping in docs/design.md.

Consequences: zero new deps, fully testable offline; swap-in to LangGraph
later without changing tool names or state fields.
