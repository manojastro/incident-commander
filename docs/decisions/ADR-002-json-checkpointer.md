# ADR-002 — JSON file checkpointer instead of Postgres for the slice

Status: accepted. Date: 2026-09-18.

Context: runs must survive a server restart while waiting for approval.

Decision: persist each `RunState` to `data/runs/<id>.json` at pause and on
every transition; resume loads from disk. Postgres checkpointer returns in
the full build.

Consequences: restart-resume works offline with zero infra; concurrent writes
are last-writer-wins (fine for a demo, noted as a limit).
