"""JSON file persistence: runs survive a server restart while waiting.

Each run is stored at <data_dir>/<run_id>.json. The API loads it on every
request, so approving after a restart simply resumes from disk.
"""

from __future__ import annotations

from pathlib import Path

from incident_commander.config import get_settings
from incident_commander.state import RunState


def runs_dir() -> Path:
    d = Path(get_settings().data_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_run(state: RunState) -> Path:
    p = runs_dir() / f"{state.run_id}.json"
    p.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return p


def load_run(run_id: str) -> RunState:
    p = runs_dir() / f"{run_id}.json"
    return RunState.model_validate_json(p.read_text(encoding="utf-8"))


def list_runs() -> list[str]:
    d = runs_dir()
    return sorted(p.stem for p in d.glob("*.json"))


def run_to_dict(state: RunState) -> dict[str, object]:
    return state.model_dump(mode="json")  # type: ignore[return-value]
