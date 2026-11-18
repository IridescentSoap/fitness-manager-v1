from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_timezone: str = "Asia/Shanghai"
    app_data_dir: Path = Path("./data")
    backup_dir: Path = Path("./backups")
    backup_retention_days: int = 30
    schedule_horizon_days: int = 365
    session_idle_hours: int = 12
    login_max_failures: int = 5
    login_lockout_seconds: int = 60
    allowed_hosts: str = "localhost,127.0.0.1"
    log_level: str = "INFO"
    app_version: str = "1.0.0"

    @property
    def database_url(self) -> str:
        db_path = (self.app_data_dir / "fitness.db").resolve()
        return f"sqlite:///{db_path.as_posix()}"

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
