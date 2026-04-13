import random
import string
from sqlalchemy.orm import Session
from db.models.sacrament import SacramentRecord
from log_config import logger


def generate_sacrament_record_reference_number(sacrament_name: str, db: Session) -> str:
    """
    Generate a unique reference number for a sacrament record.

    Format: <FIRST_3_LETTERS_OF_SACRAMENT>-<4_CHAR_RANDOM_STRING>
    Example: 'BAP-9F2K' for 'Baptism'

    The function checks for uniqueness in the database.
    Retries up to 10 times before failing.

    Args:
        sacrament_name (str): Name of the sacrament (e.g., 'Baptism', 'Marriage').
        db (Session): SQLAlchemy database session for querying existing records.

    Returns:
        str: A unique reference number.

    Raises:
        Exception: If a unique reference number could not be generated after 10 attempts.
    """
    # Convert sacrament name to uppercase and take first 3 letters (e.g. BAP, MAR)
    abbreviation = sacrament_name.strip().upper()[:3]
    attempt = 0

    while attempt < 10:
        # Generate a random alphanumeric 4-character string (e.g. 9F2K)
        unique_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        reference_no = f"{abbreviation}-{unique_suffix}"

        # Check if reference number already exists in the database
        exists = db.query(SacramentRecord).filter_by(reference_no=reference_no).first()
        if not exists:
            logger.debug("Generated unique reference number.")
            return reference_no

        # If duplicate, log warning and try again
        logger.warning("Duplicate reference number found, retrying...")
        attempt += 1

    # After 10 attempts, fail and log error
    logger.error("Failed to generate a unique reference number after multiple attempts.")
    raise Exception("Could not generate unique reference number.")
