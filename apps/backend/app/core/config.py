from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    backend_root: Path
    data_dir: Path
    logs_dir: Path
    artifacts_dir: Path
    database_url: str
    default_agent_slug: str
    default_timezone: str
    default_workspace_root: Path
    bundled_skills_root: Path
    user_skills_root: Path
    scheduler_poll_interval_seconds: float
    stale_task_run_seconds: int
    secret_backend: str
    secret_service_name: str
    default_model_provider: str
    default_model_name: str
    default_max_iterations_per_execution: int
    default_daily_budget_usd: float
    default_monthly_budget_usd: float
    default_app_view: str
    default_activity_poll_seconds: int
    default_heartbeat_interval_seconds: int
    tool_timeout_seconds: float
    shell_exec_max_timeout_seconds: float
    shell_exec_max_output_chars: int
    shell_exec_allowed_cwd_roots: tuple[str, ...]
    shell_exec_allowed_env_keys: tuple[str, ...]
    web_search_cache_ttl_seconds: int
    web_fetch_cache_ttl_seconds: int
    web_fetch_max_response_bytes: int
    web_fetch_default_max_chars: int
    bootstrap_token: str | None
    subagent_max_concurrency_per_session: int
    execution_worker_poll_interval_seconds: float
    subagent_worker_poll_interval_seconds: float
    subagent_run_timeout_seconds: float
    subagent_max_run_timeout_seconds: float
    subagent_stuck_grace_seconds: float

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)


def _resolve_backend_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def _build_settings() -> Settings:
    backend_root = _resolve_backend_root()
    data_dir = Path(os.getenv("APP_DATA_DIR", backend_root / "data"))
    logs_dir = Path(os.getenv("APP_LOG_DIR", data_dir / "logs"))
    artifacts_dir = Path(os.getenv("APP_ARTIFACTS_DIR", data_dir / "artifacts"))
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        database_url = f"sqlite:///{data_dir / 'agent_os.db'}"

    return Settings(
        app_name="Nanobot Agent Backend",
        app_version="0.2.0",
        backend_root=backend_root,
        data_dir=data_dir,
        logs_dir=logs_dir,
        artifacts_dir=artifacts_dir,
        database_url=database_url,
        default_agent_slug=os.getenv("DEFAULT_AGENT_SLUG", "main"),
        default_timezone=os.getenv("APP_TIMEZONE", "UTC"),
        default_workspace_root=Path(
            os.getenv("APP_WORKSPACE_ROOT", backend_root.parents[1])
        ).resolve(),
        bundled_skills_root=Path(
            os.getenv("APP_BUNDLED_SKILLS_ROOT", backend_root / "app" / "skills" / "bundled")
        )
        .expanduser()
        .resolve(),
        user_skills_root=Path(
            os.getenv("APP_USER_SKILLS_ROOT", Path.home() / ".forkclaw" / "skills")
        )
        .expanduser()
        .resolve(),
        scheduler_poll_interval_seconds=float(os.getenv("SCHEDULER_POLL_INTERVAL_SECONDS", "1.0")),
        stale_task_run_seconds=int(os.getenv("STALE_TASK_RUN_SECONDS", "900")),
        secret_backend=os.getenv("APP_SECRET_BACKEND", "keychain"),
        secret_service_name=os.getenv("APP_SECRET_SERVICE_NAME", "nanobot-agent-console"),
        default_model_provider=os.getenv("DEFAULT_MODEL_PROVIDER", "product_echo"),
        default_model_name=os.getenv("DEFAULT_MODEL_NAME", "product-echo/simple"),
        default_max_iterations_per_execution=int(
            os.getenv("DEFAULT_MAX_ITERATIONS_PER_EXECUTION", "2")
        ),
        default_daily_budget_usd=float(os.getenv("DEFAULT_DAILY_BUDGET_USD", "10")),
        default_monthly_budget_usd=float(os.getenv("DEFAULT_MONTHLY_BUDGET_USD", "200")),
        default_app_view=os.getenv("DEFAULT_APP_VIEW", "chat"),
        default_activity_poll_seconds=int(os.getenv("DEFAULT_ACTIVITY_POLL_SECONDS", "3")),
        default_heartbeat_interval_seconds=int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "1800")),
        tool_timeout_seconds=float(os.getenv("TOOL_TIMEOUT_SECONDS", "15.0")),
        shell_exec_max_timeout_seconds=float(os.getenv("SHELL_EXEC_MAX_TIMEOUT_SECONDS", "60.0")),
        shell_exec_max_output_chars=int(os.getenv("SHELL_EXEC_MAX_OUTPUT_CHARS", "12000")),
        shell_exec_allowed_cwd_roots=_read_env_list("SHELL_EXEC_ALLOWED_CWD_ROOTS"),
        shell_exec_allowed_env_keys=_read_env_list(
            "SHELL_EXEC_ALLOWED_ENV_KEYS",
            default=(
                "PATH",
                "HOME",
                "TMPDIR",
                "TMP",
                "TEMP",
                "LANG",
                "LC_ALL",
                "USER",
                "LOGNAME",
            ),
        ),
        web_search_cache_ttl_seconds=int(os.getenv("WEB_SEARCH_CACHE_TTL_SECONDS", "900")),
        web_fetch_cache_ttl_seconds=int(os.getenv("WEB_FETCH_CACHE_TTL_SECONDS", "900")),
        web_fetch_max_response_bytes=int(
            os.getenv("WEB_FETCH_MAX_RESPONSE_BYTES", str(512 * 1024))
        ),
        web_fetch_default_max_chars=int(os.getenv("WEB_FETCH_DEFAULT_MAX_CHARS", "8000")),
        bootstrap_token=(os.getenv("APP_BOOTSTRAP_TOKEN", "").strip() or None),
        subagent_max_concurrency_per_session=int(
            os.getenv("SUBAGENT_MAX_CONCURRENCY_PER_SESSION", "3")
        ),
        execution_worker_poll_interval_seconds=float(
            os.getenv("EXECUTION_WORKER_POLL_INTERVAL_SECONDS", "0.1")
        ),
        subagent_worker_poll_interval_seconds=float(
            os.getenv("SUBAGENT_WORKER_POLL_INTERVAL_SECONDS", "0.2")
        ),
        subagent_run_timeout_seconds=float(os.getenv("SUBAGENT_RUN_TIMEOUT_SECONDS", "3.0")),
        subagent_max_run_timeout_seconds=float(
            os.getenv("SUBAGENT_MAX_RUN_TIMEOUT_SECONDS", "30.0")
        ),
        subagent_stuck_grace_seconds=float(os.getenv("SUBAGENT_STUCK_GRACE_SECONDS", "2.0")),
    )


@lru_cache
def get_settings() -> Settings:
    return _build_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def _read_env_list(name: str, *, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return default
        if isinstance(parsed, list):
            return tuple(str(item).strip() for item in parsed if str(item).strip())
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())
