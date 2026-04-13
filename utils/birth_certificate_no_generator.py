import random
from log_config import logger


def generate_birth_certificate_no(
    parish_name: str, sacrament_name: str, index: int
) -> str:
    """
    Generate a random 8-digit birth certificate number.

    This function returns a randomly generated 8-digit string to serve
    as a certificate number. Input values are used for context only,
    but are not logged to protect sensitive data.
    """
    number = str(random.randint(10**7, 10**8 - 1))
    logger.info("Birth certificate number generated.")
    return number
