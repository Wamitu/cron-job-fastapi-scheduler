from datetime import datetime, timedelta, date
from typing import Union
from zoneinfo import ZoneInfo
from log_config import logger


def utcnow() -> datetime:
    """Return the current UTC datetime with timezone info."""
    now = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    logger.debug("Fetched current UTC time.")
    return now


def calculate_days_remaining(end: datetime) -> int:
    """Return number of days remaining until end date (0 if expired)."""
    days = max((end - utcnow()).days, 0)
    logger.info("Calculated days remaining.")
    return days


def is_subscription_expired(end: datetime) -> bool:
    """Check whether the subscription end date has passed."""
    expired = utcnow() > end
    logger.info("Checked if subscription is expired.")
    return expired


def calculate_end_date(start: datetime, days: int) -> datetime:
    """Calculate subscription end date from start date and number of days."""
    end = start + timedelta(days=days)
    logger.info("Calculated end date from start and duration.")
    return end


def get_subscription_status(start: datetime, end: datetime) -> str:
    """Return subscription status: 'pending', 'active', or 'expired'."""
    now = utcnow()
    if now < start:
        status = "pending"
    elif now > end:
        status = "expired"
    else:
        status = "active"
    logger.info("Determined subscription status.")
    return status


def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    """Return date formatted as string."""
    formatted = dt.strftime(fmt)
    logger.debug("Formatted date.")
    return formatted


def get_renewal_date(end: datetime, extension_days: int) -> datetime:
    """Return new renewal date by adding extension days to current end date."""
    renewal = end + timedelta(days=extension_days)
    logger.info("Calculated renewal date.")
    return renewal


def convert_to_timezone(dt: datetime, tz: str = "Africa/Nairobi") -> datetime:
    """Convert given datetime to the specified timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    converted = dt.astimezone(ZoneInfo(tz))
    logger.debug("Converted datetime to target timezone.")
    return converted


def get_current_time_in_timezone(tz: str = "Africa/Nairobi") -> datetime:
    """Return current time in specified timezone."""
    now = datetime.now(ZoneInfo(tz))
    logger.debug("Fetched current time in timezone.")
    return now


def is_expiring_soon(end: datetime, warning_days: int = 7) -> bool:
    """Check if subscription is expiring within the warning period."""
    remaining = calculate_days_remaining(end)
    soon = 0 < remaining <= warning_days
    logger.info("Checked if subscription is expiring soon.")
    return soon


def is_within_grace_period(end: datetime, grace_days: int = 3) -> bool:
    """Check if subscription is within the grace period after expiry."""
    expired = is_subscription_expired(end)
    days_past = abs((end - utcnow()).days)
    within = expired and days_past <= grace_days
    logger.info("Checked if within grace period.")
    return within


def get_subscription_info(start: datetime, end: datetime) -> dict:
    """Return detailed dictionary of subscription progress and status."""
    now = utcnow()
    total_days = (end - start).days
    days_elapsed = max((now - start).days, 0)
    days_remaining = calculate_days_remaining(end)
    progress = round((days_elapsed / total_days * 100), 2) if total_days > 0 else 0

    info = {
        "start_date": start,
        "end_date": end,
        "status": get_subscription_status(start, end),
        "is_expired": is_subscription_expired(end),
        "days_remaining": days_remaining,
        "days_elapsed": days_elapsed,
        "total_days": total_days,
        "progress": progress,
        "expiring_soon": is_expiring_soon(end),
        "within_grace_period": is_within_grace_period(end),
    }

    logger.info("Generated subscription info summary.")
    return info


def calculate_prorated_amount(full_price: float, start: datetime, end: datetime, from_date: datetime) -> float:
    """Calculate the prorated subscription price from a specific date."""
    total_days = (end - start).days
    remaining_days = (end - from_date).days
    prorated = max((remaining_days / total_days) * full_price, 0.0) if total_days > 0 else 0.0
    logger.info("Calculated prorated subscription amount.")
    return prorated


def get_next_billing_date(end: datetime, cycle_days: int) -> datetime:
    """Return the next billing date after a given cycle duration."""
    next_date = end + timedelta(days=cycle_days)
    logger.info("Computed next billing date.")
    return next_date


def validate_date_range(start: datetime, end: datetime) -> bool:
    """Ensure the end date is after the start date."""
    valid = end > start
    logger.info("Validated date range.")
    return valid


def normalize_datetime(dt: Union[datetime, date, str]) -> datetime:
    """
    Convert date, datetime or ISO 8601 string to a datetime object.
    Raises ValueError on unsupported types or parse failure.
    """
    try:
        if isinstance(dt, str):
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            logger.debug("Normalized ISO string datetime.")
            return parsed
        elif isinstance(dt, date) and not isinstance(dt, datetime):
            combined = datetime.combine(dt, datetime.min.time())
            logger.debug("Normalized date object to datetime.")
            return combined
        elif isinstance(dt, datetime):
            logger.debug("Datetime already normalized.")
            return dt
    except Exception as e:
        logger.error(f"Failed to normalize datetime: {e.__class__.__name__}")
        raise

    raise ValueError("Unsupported date type provided for normalization.")


# Constants
class DateConstants:
    """Useful constants for date calculations and durations."""
    DAYS_IN_MONTH = 30
    DEFAULT_WARNING_DAYS = 7
    DEFAULT_GRACE_PERIOD = 3
    TRIAL_DAYS = 14
    MONTHLY = 30
    QUARTERLY = 90
    YEARLY = 365
