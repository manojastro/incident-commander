"""Stub MCP tools, in-process (offline). Each has output caps."""

from __future__ import annotations

from typing import Any, cast

from incident_commander.scenarios import SCENARIOS

MAX_LOG_LINES = 20
MAX_LOG_CHARS = 200
MAX_CHANGES = 10
MAX_BLAST = 15
MAX_KEDB = 5


def _truncate(s: str, n: int = MAX_LOG_CHARS) -> str:
    return s if len(s) <= n else s[:n] + "…"


class ToolError(RuntimeError):
    pass


_FAIL_LOGS = False


def set_fail_logs(flag: bool) -> None:
    global _FAIL_LOGS
    _FAIL_LOGS = flag


def _scenario(incident_number: str) -> dict[str, object]:
    if incident_number not in SCENARIOS:
        raise ToolError(f"unknown incident {incident_number}")
    return SCENARIOS[incident_number]


def get_incident(incident_number: str) -> dict[str, object]:
    sc = _scenario(incident_number)
    return {
        "number": incident_number,
        "title": str(sc["title"]),
        "description": str(sc["description"]),
        "service": str(sc["service"]),
        "opened_at": "2026-09-18T10:00:00Z",
        "status": "New",
    }


def get_logs(service: str, incident_number: str = "") -> dict[str, object]:
    """Return capped log lines for the incident's service."""
    if _FAIL_LOGS:
        raise ToolError("get_logs timed out after 5s (simulated)")
    sc = _scenario(incident_number) if incident_number else None
    raw: list[str] = cast(list[str], sc["logs"]) if sc else [f"INFO {service} no anomalies"]
    lines = raw[:MAX_LOG_LINES]
    return {"service": service, "lines": [_truncate(x) for x in lines]}


def list_recent_changes(
    service: str, incident_number: str = "", window_min: int = 60
) -> dict[str, object]:
    sc = _scenario(incident_number) if incident_number else None
    changes: list[dict[str, Any]] = []
    if sc is not None:
        all_changes = cast(list[dict[str, Any]], sc["changes"])
        changes = [c for c in all_changes if int(c.get("age_min", 999)) <= window_min][:MAX_CHANGES]
    return {"service": service, "changes": changes}


def get_blast_radius(ci: str, incident_number: str = "") -> dict[str, object]:
    sc = _scenario(incident_number) if incident_number else None
    radius: list[str] = cast(list[str], sc["blast_radius"]) if sc is not None else [ci]
    return {"ci": ci, "affected": radius[:MAX_BLAST]}


def search_kedb(query: str, incident_number: str = "") -> dict[str, object]:
    sc = _scenario(incident_number) if incident_number else None
    hits: list[dict[str, Any]] = cast(list[dict[str, Any]], sc["kedb"]) if sc is not None else []
    return {"query": query[:120], "hits": hits[:MAX_KEDB]}
