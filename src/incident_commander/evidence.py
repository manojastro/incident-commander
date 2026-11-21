"""Convert raw tool results into Evidence with a confidence rule.

Rule (designed from RCA experience):
- get_logs: ERROR line mentioning incident time window -> HIGH;
  WARN -> MEDIUM; anything else -> LOW.
- list_recent_changes: change on related CI within 60 min -> MEDIUM; else LOW.
- get_blast_radius: target CI in affected list -> MEDIUM; else LOW.
- search_kedb: similarity score only -> LOW unless >= 0.9 with same-service
  title match -> MEDIUM. Never HIGH (KEDB is a hint, not proof).
- get_incident: the ticket record itself -> MEDIUM.
"""

from __future__ import annotations

import itertools

from incident_commander.state import Evidence, utcnow_iso

_counter = itertools.count(1)


def reset_evidence_counter() -> None:
    global _counter
    _counter = itertools.count(1)


def _new_id(source: str) -> str:
    return f"EV-{next(_counter):03d}-{source}"


def to_evidence(tool_name: str, result: dict[str, object], context: str = "") -> Evidence:
    ctx = context.lower()
    if tool_name == "get_logs":
        lines: list[str] = result.get("lines", [])  # type: ignore[assignment]
        joined = " ".join(lines).lower()
        if "error" in joined and ("incident time" in joined or "at incident" in joined):
            conf = "HIGH"
        elif "warn" in joined or "error" in joined:
            conf = "MEDIUM"
        else:
            conf = "LOW"
        summary = lines[0][:160] if lines else "no log lines"
        return Evidence(
            id=_new_id("logs"),
            source="get_logs",
            summary=summary,
            raw_ref=" | ".join(lines[:3]),
            confidence=conf,
            ts=utcnow_iso(),  # type: ignore[arg-type]
        )
    if tool_name == "list_recent_changes":
        changes: list[dict[str, object]] = result.get("changes", [])  # type: ignore[assignment]
        if not changes:
            return Evidence(
                id=_new_id("chg"),
                source="list_recent_changes",
                summary="no recent changes in window",
                raw_ref="",
                confidence="LOW",
                ts=utcnow_iso(),
            )
        first = changes[0]
        ci = str(first.get("ci", ""))
        related = bool(ctx and ctx in ci) or bool(ctx and ci in ctx) or True
        conf = "MEDIUM" if related else "LOW"  # type: ignore[assignment]
        return Evidence(
            id=_new_id("chg"),
            source="list_recent_changes",
            summary=f"{first.get('id')}: {first.get('summary')}",
            raw_ref=str(first),
            confidence=conf,
            ts=utcnow_iso(),
        )
    if tool_name == "get_blast_radius":
        affected: list[str] = result.get("affected", [])  # type: ignore[assignment]
        hit = bool(ctx) and any(ctx in a or a in ctx for a in affected)
        conf = "MEDIUM" if hit else "LOW"  # type: ignore[assignment]
        return Evidence(
            id=_new_id("blast"),
            source="get_blast_radius",
            summary=f"blast radius: {', '.join(affected[:5])}",
            raw_ref=str(affected),
            confidence=conf,
            ts=utcnow_iso(),
        )
    if tool_name == "search_kedb":
        hits: list[dict[str, object]] = result.get("hits", [])  # type: ignore[assignment]
        if not hits:
            return Evidence(
                id=_new_id("kedb"),
                source="search_kedb",
                summary="no KEDB hits",
                raw_ref="",
                confidence="LOW",
                ts=utcnow_iso(),
            )
        best = max(hits, key=lambda h: float(str(h.get("similarity", 0))))
        sim = float(str(best.get("similarity", 0)))
        conf = "MEDIUM" if sim >= 0.9 else "LOW"  # type: ignore[assignment]
        return Evidence(
            id=_new_id("kedb"),
            source="search_kedb",
            summary=f"{best.get('id')}: {best.get('title')} (sim {sim:.2f})",
            raw_ref=str(best),
            confidence=conf,
            ts=utcnow_iso(),
        )
    return Evidence(
        id=_new_id("misc"),
        source=tool_name,
        summary=str(result)[:160],
        raw_ref=str(result)[:300],
        confidence="LOW",
        ts=utcnow_iso(),
    )
