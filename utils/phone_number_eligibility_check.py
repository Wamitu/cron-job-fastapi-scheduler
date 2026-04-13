import re
from log_config import logger


def is_valid_phone_number(phone: str) -> bool:
    """
    Validate whether a given string is a valid Kenyan phone number.

    Requirements:
    - Must start with '2547'
    - Must be exactly 12 digits long (e.g., 254712345678)

    Args:
        phone (str): The phone number string to validate

    Returns:
        bool: True if valid, False otherwise
    """
    logger.debug("Validating phone number format.")

    if not phone:
        logger.warning("Phone number is missing or None.")
        return False

    pattern = r"^2547\d{8}$"
    is_valid = bool(re.match(pattern, phone))

    if is_valid:
        logger.info("Phone number is valid.")
    else:
        logger.warning("Phone number is invalid.")

    return is_valid
