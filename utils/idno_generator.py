import random
from log_config import logger


def generate_idno() -> str:
    """
    Generate a random 8-digit national ID-like number as a string.

    Returns:
        str: An 8-digit numeric string (e.g., '12345678')
    """
    # Generate a random number between 10,000,000 and 99,999,999 (inclusive)
    idno = str(random.randint(10_000_000, 99_999_999))

    # Log success without exposing the actual number for privacy/security reasons
    logger.info("Generated new ID number.")

    return idno
