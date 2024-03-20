from datetime import datetime, timezone


def utc_from_timestamp(timestamp: float) -> datetime:
    """Return UTC time from a timestamp."""
    return datetime.fromtimestamp(timestamp, timezone.utc)
