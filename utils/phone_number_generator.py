import random

from sqlalchemy import text

from db.models.member import Member
from db.models.user import User
from log_config import logger


def generate_unique_phone(db):
    """
    Generate a unique Kenyan phone number (starting with 2547) that does not exist
    in any of the following:
      - User.phone field
      - Member.member_data JSON field -> phone
      - Member.member_data JSON field -> next_of_kin_details -> phone

    Args:
        db (Session): SQLAlchemy database session

    Returns:
        str: A unique phone number string (e.g. '254712345678')
    """
    attempt = 0
    while True:
        attempt += 1
        # Generate a random 8-digit number and prefix with '2547'
        phone = f"2547{random.randint(10000000, 99999999)}"
        logger.debug(f"Attempt {attempt}: Generating phone number.")

        # Check if phone exists in User table
        user_exists = db.query(User).filter_by(phone=phone).first()
        if user_exists:
            logger.debug("Phone already exists in user records.")
            continue

        # Check if phone exists in Member.member_data.phone (JSONB field)
        member_phone_exists = (
            db.query(Member)
            .filter(text("member_data->>'phone' = :phone"))
            .params(phone=phone)
            .first()
        )
        if member_phone_exists:
            logger.debug("Phone already exists in member data.")
            continue

        # Check if phone exists in Member.member_data.next_of_kin_details.phone
        next_of_kin_phone_exists = (
            db.query(Member)
            .filter(text("member_data->'next_of_kin_details'->>'phone' = :phone"))
            .params(phone=phone)
            .first()
        )
        if next_of_kin_phone_exists:
            logger.debug("Phone already exists in next-of-kin data.")
            continue

        # All checks passed — phone number is unique
        logger.info("Unique phone number generated successfully.")
        return phone
