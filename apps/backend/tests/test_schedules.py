import pytest
from datetime import timedelta
from app.core.schedules import parse_schedule, ParsedSchedule


def test_parse_schedule_valid_interval():
    # Valid intervals with different units
    res = parse_schedule("every:30s", "UTC")
    assert res == ParsedSchedule(
        schedule="every:30s", timezone="UTC", kind="interval", interval=timedelta(seconds=30)
    )

    res = parse_schedule("every:5m", "America/New_York")
    assert res == ParsedSchedule(
        schedule="every:5m", timezone="America/New_York", kind="interval", interval=timedelta(minutes=5)
    )

    res = parse_schedule("every:2h", "UTC")
    assert res == ParsedSchedule(
        schedule="every:2h", timezone="UTC", kind="interval", interval=timedelta(hours=2)
    )

    res = parse_schedule("every:1d", "UTC")
    assert res == ParsedSchedule(
        schedule="every:1d", timezone="UTC", kind="interval", interval=timedelta(days=1)
    )

    # Normalization check (uppercase, spaces)
    res = parse_schedule("  EVERY:15M  ", "UTC")
    assert res == ParsedSchedule(
        schedule="every:15m", timezone="UTC", kind="interval", interval=timedelta(minutes=15)
    )


def test_parse_schedule_valid_daily():
    res = parse_schedule("daily:09:30", "UTC")
    assert res == ParsedSchedule(
        schedule="daily:09:30", timezone="UTC", kind="daily", hour=9, minute=30
    )


def test_parse_schedule_valid_weekly():
    res = parse_schedule("weekly:mon@14:00", "UTC")
    assert res == ParsedSchedule(
        schedule="weekly:mon@14:00", timezone="UTC", kind="weekly", weekday=0, hour=14, minute=0
    )

    res = parse_schedule("weekly:sun@00:00", "UTC")
    assert res == ParsedSchedule(
        schedule="weekly:sun@00:00", timezone="UTC", kind="weekly", weekday=6, hour=0, minute=0
    )


def test_parse_schedule_invalid_interval_value():
    with pytest.raises(ValueError, match="Interval schedule must be greater than zero."):
        parse_schedule("every:0s", "UTC")

    with pytest.raises(ValueError, match="Invalid schedule. Use `every:30s`, `every:5m`, `daily:09:00`, or `weekly:mon@09:00`."):
        parse_schedule("every:-5m", "UTC")


def test_parse_schedule_invalid_clock():
    with pytest.raises(ValueError, match="Invalid hour or minute in schedule."):
        parse_schedule("daily:24:00", "UTC")

    with pytest.raises(ValueError, match="Invalid hour or minute in schedule."):
        parse_schedule("daily:12:60", "UTC")

    with pytest.raises(ValueError, match="Invalid hour or minute in schedule."):
        parse_schedule("weekly:mon@25:00", "UTC")


def test_parse_schedule_invalid_timezone():
    with pytest.raises(ValueError, match="Invalid timezone: Invalid/Zone"):
        parse_schedule("daily:09:00", "Invalid/Zone")

    with pytest.raises(ValueError, match="Invalid timezone: Invalid/Zone"):
        parse_schedule("weekly:tue@12:00", "Invalid/Zone")

    # Interval parsing doesn't validate timezone directly at parse time in this implementation
    # It just stores it. But that's fine according to code logic.


def test_parse_schedule_completely_invalid_format():
    with pytest.raises(ValueError, match="Invalid schedule. Use `every:30s`, `every:5m`, `daily:09:00`, or `weekly:mon@09:00`."):
        parse_schedule("random string", "UTC")

    with pytest.raises(ValueError, match="Invalid schedule. Use `every:30s`, `every:5m`, `daily:09:00`, or `weekly:mon@09:00`."):
        parse_schedule("yearly:01-01", "UTC")
