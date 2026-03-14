from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from app.core.config import get_settings
from app.core.provider_catalog import get_default_model, normalize_provider_id
from app.core.secrets import get_secret_store
from app.models.entities import Agent, AgentProfile
from app.repositories.operational_settings import OperationalSettingsRepository
from app.schemas.operational_settings import (
    OperationalSettingsRead,
    OperationalSettingsUpdate,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OperationalRuntimeConfig:
    provider: str
    model_name: str
    workspace_root: str
    max_iterations_per_execution: int
    daily_budget_usd: float
    monthly_budget_usd: float


class OperationalSettingsService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = OperationalSettingsRepository(session)
        self.secret_store = get_secret_store()

    def get_operational_settings(self) -> OperationalSettingsRead:
        _, profile = self._require_default_bundle()
        return self._build_read_model(profile)

    def update_operational_settings(
        self,
        payload: OperationalSettingsUpdate,
    ) -> OperationalSettingsRead:
        agent, profile = self._require_default_bundle()
        provider = normalize_provider_id(payload.provider)
        model_name = payload.model_name.strip()
        workspace_root = Path(payload.workspace_root).expanduser().resolve()
        if not workspace_root.exists() or not workspace_root.is_dir():
            msg = "Workspace root must point to an existing directory."
            raise ValueError(msg)

        if payload.monthly_budget_usd < payload.daily_budget_usd:
            msg = "Monthly budget must be greater than or equal to the daily budget."
            raise ValueError(msg)

        self.repository.upsert_setting(
            scope="runtime",
            key="default_model_provider",
            value_type="string",
            value_text=provider,
        )
        self.repository.upsert_setting(
            scope="runtime",
            key="default_model_name",
            value_type="string",
            value_text=model_name,
        )
        self.repository.upsert_setting(
            scope="runtime",
            key="max_iterations_per_execution",
            value_type="integer",
            value_text=str(payload.max_iterations_per_execution),
        )
        self.repository.upsert_setting(
            scope="runtime",
            key="heartbeat_interval_seconds",
            value_type="integer",
            value_text=str(payload.heartbeat_interval_seconds),
        )
        self.repository.upsert_setting(
            scope="budget",
            key="daily_usd",
            value_type="float",
            value_text=f"{payload.daily_budget_usd:.6f}",
        )
        self.repository.upsert_setting(
            scope="budget",
            key="monthly_usd",
            value_type="float",
            value_text=f"{payload.monthly_budget_usd:.6f}",
        )
        self.repository.upsert_setting(
            scope="security",
            key="workspace_root",
            value_type="string",
            value_text=str(workspace_root),
        )
        self.repository.upsert_setting(
            scope="preferences",
            key="default_view",
            value_type="string",
            value_text=payload.default_view,
        )
        self.repository.upsert_setting(
            scope="preferences",
            key="activity_poll_seconds",
            value_type="integer",
            value_text=str(payload.activity_poll_seconds),
        )

        profile.model_provider = provider
        profile.model_name = model_name
        self.repository.save_profile(profile)
        self.repository.update_workspace_permissions(agent.id, str(workspace_root))

        if payload.clear_api_key:
            self.secret_store.delete_provider_api_key(provider)
        elif provider != "product_echo" and payload.api_key:
            self.secret_store.set_provider_api_key(provider, payload.api_key.strip())

        self.repository.record_audit_event(
            agent_id=agent.id,
            event_type="settings.operational.updated",
            entity_type="setting",
            entity_id=agent.id,
            payload={
                "provider": provider,
                "model_name": model_name,
                "workspace_root": str(workspace_root),
                "max_iterations_per_execution": payload.max_iterations_per_execution,
                "daily_budget_usd": payload.daily_budget_usd,
                "monthly_budget_usd": payload.monthly_budget_usd,
                "default_view": payload.default_view,
                "activity_poll_seconds": payload.activity_poll_seconds,
                "heartbeat_interval_seconds": payload.heartbeat_interval_seconds,
                "api_key_configured": bool(payload.api_key and provider != "product_echo"),
                "api_key_cleared": payload.clear_api_key,
            },
            summary_text="Operational settings updated.",
        )
        return self._build_read_model(profile, workspace_root=workspace_root)

    def resolve_runtime_config(self, profile: AgentProfile) -> OperationalRuntimeConfig:
        current = self._build_read_model(profile)
        return OperationalRuntimeConfig(
            provider=current.provider,
            model_name=current.model_name,
            workspace_root=current.workspace_root,
            max_iterations_per_execution=current.max_iterations_per_execution,
            daily_budget_usd=current.daily_budget_usd,
            monthly_budget_usd=current.monthly_budget_usd,
        )

    def enforce_budget_limits(self, *, input_text: str) -> None:
        agent, profile = self._require_default_bundle()
        runtime = self.resolve_runtime_config(profile)
        projected_cost = self.estimate_input_cost(input_text)
        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        daily_spend = self.repository.sum_estimated_cost_since(agent.id, day_start)
        monthly_spend = self.repository.sum_estimated_cost_since(agent.id, month_start)

        if daily_spend + projected_cost > runtime.daily_budget_usd:
            self.repository.record_audit_event(
                agent_id=agent.id,
                event_type="budget.daily_blocked",
                entity_type="agent",
                entity_id=agent.id,
                payload={
                    "daily_spend": daily_spend,
                    "projected_cost": projected_cost,
                    "daily_budget_usd": runtime.daily_budget_usd,
                },
                level="warning",
                summary_text="Execution blocked by the daily budget limit.",
            )
            msg = "Daily budget exceeded for this projected execution."
            raise ValueError(msg)

        if monthly_spend + projected_cost > runtime.monthly_budget_usd:
            self.repository.record_audit_event(
                agent_id=agent.id,
                event_type="budget.monthly_blocked",
                entity_type="agent",
                entity_id=agent.id,
                payload={
                    "monthly_spend": monthly_spend,
                    "projected_cost": projected_cost,
                    "monthly_budget_usd": runtime.monthly_budget_usd,
                },
                level="warning",
                summary_text="Execution blocked by the monthly budget limit.",
            )
            msg = "Monthly budget exceeded for this projected execution."
            raise ValueError(msg)

    def _require_default_bundle(self) -> tuple[Agent, AgentProfile]:
        agent = self.repository.get_default_agent()
        if agent is None:
            msg = "Default agent not found."
            raise ValueError(msg)

        profile = self.repository.get_profile(agent.id)
        if profile is None:
            msg = "Agent profile not found."
            raise ValueError(msg)

        return agent, profile

    @staticmethod
    def estimate_input_cost(input_text: str) -> float:
        normalized = max(len(input_text.strip()), 1)
        estimated_tokens = max(normalized // 4, 1)
        return round(estimated_tokens * 0.000002, 6)

    def _build_read_model(
        self,
        profile: AgentProfile,
        *,
        workspace_root: Path | None = None,
    ) -> OperationalSettingsRead:
        settings = get_settings()
        provider = normalize_provider_id(
            self._get_text_setting(
                "runtime",
                "default_model_provider",
                profile.model_provider or settings.default_model_provider,
            )
        )
        model_name = self._resolve_model_name(
            provider=provider,
            profile=profile,
            app_default_provider=settings.default_model_provider,
            app_default_model=settings.default_model_name,
        )
        resolved_workspace_root = (
            workspace_root
            or Path(
                self._get_text_setting(
                    "security",
                    "workspace_root",
                    str(settings.default_workspace_root),
                )
            ).resolve()
        )

        return OperationalSettingsRead(
            provider=provider,
            model_name=model_name,
            workspace_root=str(resolved_workspace_root),
            max_iterations_per_execution=self._get_int_setting(
                "runtime",
                "max_iterations_per_execution",
                settings.default_max_iterations_per_execution,
            ),
            daily_budget_usd=self._get_float_setting(
                "budget",
                "daily_usd",
                settings.default_daily_budget_usd,
            ),
            monthly_budget_usd=self._get_float_setting(
                "budget",
                "monthly_usd",
                settings.default_monthly_budget_usd,
            ),
            default_view=self._get_text_setting(
                "preferences",
                "default_view",
                settings.default_app_view,
            ),
            activity_poll_seconds=self._get_int_setting(
                "preferences",
                "activity_poll_seconds",
                settings.default_activity_poll_seconds,
            ),
            heartbeat_interval_seconds=self._get_int_setting(
                "runtime",
                "heartbeat_interval_seconds",
                settings.default_heartbeat_interval_seconds,
            ),
            provider_api_key_configured=bool(
                provider != "product_echo" and self.secret_store.get_provider_api_key(provider)
            ),
        )

    def _resolve_model_name(
        self,
        *,
        provider: str,
        profile: AgentProfile,
        app_default_provider: str,
        app_default_model: str,
    ) -> str:
        setting = self.repository.get_setting("runtime", "default_model_name")
        if setting and setting.value_text and setting.value_text.strip():
            return setting.value_text.strip()

        profile_provider = (profile.model_provider or "").strip()
        if profile_provider:
            try:
                if normalize_provider_id(profile_provider) == provider and profile.model_name:
                    model_name = profile.model_name.strip()
                    if model_name:
                        return model_name
            except ValueError:
                logger.warning(
                    "Failed to normalize profile provider '%s'",
                    profile_provider,
                    exc_info=True,
                )

        try:
            default_provider = normalize_provider_id(app_default_provider)
        except ValueError:
            default_provider = "product_echo"

        if default_provider == provider:
            model_name = app_default_model.strip()
            if model_name:
                return model_name

        return get_default_model(provider)

    def _get_text_setting(self, scope: str, key: str, default: str) -> str:
        setting = self.repository.get_setting(scope, key)
        if setting and setting.value_text:
            return setting.value_text
        return default

    def _get_int_setting(self, scope: str, key: str, default: int) -> int:
        setting = self.repository.get_setting(scope, key)
        if setting and setting.value_text:
            try:
                return int(setting.value_text)
            except ValueError:
                return default
        return default

    def _get_float_setting(self, scope: str, key: str, default: float) -> float:
        setting = self.repository.get_setting(scope, key)
        if setting and setting.value_text:
            try:
                return float(setting.value_text)
            except ValueError:
                return default
        return default
