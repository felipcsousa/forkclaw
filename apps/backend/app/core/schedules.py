from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

INTERVAL_PATTERN = re.compile(r"^every:(?P<value>\d+)(?P<unit>[smhd])$")
DAILY_PATTERN = re.compile(r"^daily:(?P<hour>\d{2}):(?P<minute>\d{2})$")
WEEKLY_PATTERN = re.compile(
    r"^weekly:(?P<day>mon|tue|wed|thu|fri|sat|sun)@(?P<hour>\d{2}):(?P<minute>\d{2})$"
)
WEEKDAY_INDEX = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


@dataclass(frozen=True)
class ParsedSchedule:
    schedule: str
    timezone: str
    kind: str
    interval: timedelta | None = None
    hour: int | None = None
    minute: int | None = None
    weekday: int | None = None

    def next_after(
        self,
        *,
        reference_utc: datetime,
        last_run_at: datetime | None = None,
    ) -> datetime:
        if self.kind == "interval":
            assert self.interval is not None
            candidate = (last_run_at or reference_utc) + self.interval
            while candidate <= reference_utc:
                candidate += self.interval
            return candidate

        timezone = ZoneInfo(self.timezone)
        reference_local = reference_utc.astimezone(timezone)

        if self.kind == "daily":
            assert self.hour is not None
            assert self.minute is not None
            candidate = reference_local.replace(
                hour=self.hour,
                minute=self.minute,
                second=0,
                microsecond=0,
            )
            if candidate <= reference_local:
                candidate = candidate + timedelta(days=1)
            return candidate.astimezone(UTC)

        assert self.weekday is not None
        assert self.hour is not None
        assert self.minute is not None
        days_ahead = (self.weekday - reference_local.weekday()) % 7
        candidate = reference_local.replace(
            hour=self.hour,
            minute=self.minute,
            second=0,
            microsecond=0,
        ) + timedelta(days=days_ahead)
        if candidate <= reference_local:
            candidate = candidate + timedelta(days=7)
        return candidate.astimezone(UTC)


def parse_schedule(schedule: str, timezone: str) -> ParsedSchedule:
    normalized = schedule.strip().lower()
    interval_match = INTERVAL_PATTERN.match(normalized)
    if interval_match:
        value = int(interval_match.group("value"))
        unit = interval_match.group("unit")
        if value <= 0:
            msg = "Interval schedule must be greater than zero."
            raise ValueError(msg)
        seconds_by_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        return ParsedSchedule(
            schedule=normalized,
            timezone=timezone,
            kind="interval",
            interval=timedelta(seconds=value * seconds_by_unit[unit]),
        )

    daily_match = DAILY_PATTERN.match(normalized)
    if daily_match:
        hour = int(daily_match.group("hour"))
        minute = int(daily_match.group("minute"))
        _validate_clock(hour, minute)
        _validate_timezone(timezone)
        return ParsedSchedule(
            schedule=normalized,
            timezone=timezone,
            kind="daily",
            hour=hour,
            minute=minute,
        )

    weekly_match = WEEKLY_PATTERN.match(normalized)
    if weekly_match:
        hour = int(weekly_match.group("hour"))
        minute = int(weekly_match.group("minute"))
        _validate_clock(hour, minute)
        _validate_timezone(timezone)
        return ParsedSchedule(
            schedule=normalized,
            timezone=timezone,
            kind="weekly",
            weekday=WEEKDAY_INDEX[weekly_match.group("day")],
            hour=hour,
            minute=minute,
        )

    msg = "Invalid schedule. Use `every:30s`, `every:5m`, `daily:09:00`, or `weekly:mon@09:00`."
    raise ValueError(msg)


def _validate_clock(hour: int, minute: int) -> None:
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        msg = "Invalid hour or minute in schedule."
        raise ValueError(msg)


def _validate_timezone(timezone: str) -> None:
    try:
        ZoneInfo(timezone)
    except Exception as exc:  # pragma: no cover - zoneinfo raises varying exceptions
        msg = f"Invalid timezone: {timezone}"
        raise ValueError(msg) from exc
