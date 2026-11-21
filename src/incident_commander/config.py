"""Runtime config via env. Offline, synthetic Acme only."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "incident-commander"
    max_steps_per_run: int = 12
    max_usd_per_run: float = 0.50
    run_timeout_s: float = 60.0
    # Mock LLM cost model: fixed USD per node step (offline, no real LLM keys).
    usd_per_step: float = 0.01
    tokens_per_step: int = 350
    data_dir: str = "data/runs"
    reports_dir: str = "reports/runs"
    # Comma-separated allowlist override not needed; kept explicit in guards.
    log_level: str = "INFO"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
