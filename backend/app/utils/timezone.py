"""
Indian Standard Time (IST, UTC+05:30) utilities.
Zero external dependencies (uses standard library datetime.timezone).
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

# Indian Standard Time is fixed at UTC+05:30 (no daylight saving)
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def get_ist_now() -> datetime:
    """Return the current timestamp in Indian Standard Time (IST)."""
    return datetime.now(IST)


def to_ist(dt: datetime) -> datetime:
    """Convert any datetime object (naive or aware) to IST."""
    if dt is None:
        return get_ist_now()
    if dt.tzinfo is None:
        # Assume UTC if naive, then convert to IST
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def parse_ist_datetime(
    date_str: str,
    time_str: Optional[str] = None,
    default_time: str = "12:00",
) -> datetime:
    """
    Parse a date string (YYYY-MM-DD) and optional time string (HH:MM or HH:MM:SS)
    into an IST-aware datetime object.
    Supports ISO strings as well (e.g. '2026-09-12T14:00:00').
    """
    clean_date = date_str.strip()
    
    # Handle ISO datetime string directly if passed as date_str
    if "T" in clean_date:
        try:
            # Strip trailing Z if present and parse
            dt_iso = datetime.fromisoformat(clean_date.replace("Z", "+00:00"))
            return to_ist(dt_iso)
        except Exception:
            clean_date = clean_date.split("T")[0]

    # Clean time string
    clean_time = (time_str or "").strip()
    if not clean_time:
        clean_time = default_time

    # Normalize HH:MM vs HH:MM:SS
    parts = clean_time.split(":")
    hours = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 12
    minutes = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    seconds = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

    # Parse date (YYYY-MM-DD)
    date_parts = [int(p) for p in clean_date.split("-") if p.isdigit()]
    if len(date_parts) == 3:
        year, month, day = date_parts
    else:
        now = get_ist_now()
        year, month, day = now.year, now.month, now.day

    return datetime(year, month, day, hours, minutes, seconds, tzinfo=IST)


def format_ist_date(dt: datetime) -> str:
    """Format datetime as YYYY-MM-DD in IST."""
    return to_ist(dt).strftime("%Y-%m-%d")


def format_ist_time(dt: datetime) -> str:
    """Format datetime as HH:MM in IST (24-hour)."""
    return to_ist(dt).strftime("%H:%M")


def format_ist_time_12hr(dt: datetime) -> str:
    """Format datetime as hh:mm AM/PM in IST."""
    ist_dt = to_ist(dt)
    return ist_dt.strftime("%I:%M %p").lstrip("0") or ist_dt.strftime("%I:%M %p")


def format_ist_datetime_display(dt: datetime) -> str:
    """Format datetime as 'DD/MM/YYYY, hh:mm AM/PM' in IST."""
    ist_dt = to_ist(dt)
    time_str = format_ist_time_12hr(ist_dt)
    return f"{ist_dt.strftime('%d/%m/%Y')}, {time_str}"


def extract_booking_datetimes(b: dict) -> tuple[datetime, datetime]:
    """
    Extract IST-aware (checkin_datetime, checkout_datetime) from a booking document.
    Handles:
    - checkin_datetime / checkout_datetime if already populated
    - checkin date + checkin_time (default "12:00")
    - checkout date + checkout_time (default "11:00")
    """
    ci_dt = b.get("checkin_datetime")
    if ci_dt:
        if isinstance(ci_dt, str):
            ci_dt = parse_ist_datetime(ci_dt)
        else:
            ci_dt = to_ist(ci_dt)
    else:
        ci_dt = parse_ist_datetime(
            str(b.get("checkin", "")),
            str(b.get("checkin_time", "") or "12:00"),
            default_time="12:00",
        )

    co_dt = b.get("checkout_datetime")
    if co_dt:
        if isinstance(co_dt, str):
            co_dt = parse_ist_datetime(co_dt)
        else:
            co_dt = to_ist(co_dt)
    else:
        co_dt = parse_ist_datetime(
            str(b.get("checkout", "")),
            str(b.get("checkout_time", "") or "11:00"),
            default_time="11:00",
        )

    return ci_dt, co_dt
