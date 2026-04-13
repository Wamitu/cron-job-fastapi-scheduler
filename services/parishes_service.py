from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import String, cast
from db.models.diocese import Diocese
from db.models.parish import Parish
from log_config import logger
from utils.parish_slug_generator import generate_unique_slug
from utils.phone_number_eligibility_check import is_valid_phone_number


def check_parishes_exist(db: Session) -> bool:
    """
    Check if any parishes exist in the database.
    """
    return db.query(Parish.id).first() is not None


def create_parishes(db: Session):
    """
    Seed default parishes into the database if not already present.
    """
    parish_list = [
        {
            "parish_data": {
                "parish_name": "St. Mark Parish",
                "contact_email": "contact@stmark.org",
                "contact_phone": "254712345678",
            },
            "member_number_prefix": "SMP",
            "member_number_suffix": "100",
        },
        {
            "parish_data": {
                "parish_name": "St. Luke Parish",
                "contact_email": "contact@stluke.org",
                "contact_phone": "254798765432",
            },
            "member_number_prefix": "SLP",
            "member_number_suffix": "200",
        },
        {
            "parish_data": {
                "parish_name": "St. Paul Parish",
                "contact_email": "contact@stpaul.org",
                "contact_phone": "254701112233",
            },
            "member_number_prefix": "SPP",
            "member_number_suffix": "300",
        },
        {
            "parish_data": {
                "parish_name": "St. Mary Parish",
                "contact_email": "contact@stmary.org",
                "contact_phone": "254722334455",
            },
            "member_number_prefix": "SMA",
            "member_number_suffix": "400",
        },
        {
            "parish_data": {
                "parish_name": "Holy Basilica Parish",
                "contact_email": "contact@holybasilica.org",
                "contact_phone": "254733445566",
            },
            "member_number_prefix": "SJP",
            "member_number_suffix": "500",
        },
    ]

    nairobi_diocese = db.query(Diocese).filter(Diocese.name == "Nairobi").first()
    if not nairobi_diocese:
        raise HTTPException(status_code=400, detail="Nairobi diocese not found.")
    for parish in parish_list:
        try:
            parish_name = parish["parish_data"]["parish_name"]
            email = parish["parish_data"]["contact_email"].lower()
            phone = parish["parish_data"]["contact_phone"]
            prefix = parish["member_number_prefix"]

            # Validate phone number format
            if not is_valid_phone_number(phone):
                logger.warning("Invalid phone number format! Skipping...")
                continue

            # Check for conflicts
            if (
                db.query(Parish)
                .filter(cast(Parish.parish_data["contact_email"], String) == email)
                .first()
            ):
                logger.warning("Email already exist! Skipping...")
                continue

            if (
                db.query(Parish)
                .filter(cast(Parish.parish_data["contact_phone"], String) == phone)
                .first()
            ):
                logger.warning(f"Phone number already exists! Skipping...")
                continue

            if db.query(Parish).filter(Parish.member_number_prefix == prefix).first():
                logger.warning("Duplicate found member prefix for parish! Skipping...")
                continue

            # Generate and assign unique slug
            slug = generate_unique_slug(parish_name, db)
            parish["parish_data"]["parish_slug"] = slug

            # Create Parish instance
            new_parish = Parish(
                diocese_id=nairobi_diocese.id,
                parish_data=parish["parish_data"],
                member_number_prefix=prefix,
                member_number_suffix=parish["member_number_suffix"],
                parish_settings=None,
                is_archived=False,
            )
            db.add(new_parish)
            logger.info("Parish added to seed queue!")

        except SQLAlchemyError as e:
            logger.error("Database error while adding parish: {e.__class__.__name__}")
            db.rollback()

    try:
        db.commit()
        logger.info("Parish seeding completed.")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Parish seeding commit failed: {e.__class__.__name__}")
