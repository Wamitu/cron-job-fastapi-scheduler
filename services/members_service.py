import random
import uuid
import time
import logging
from collections import defaultdict
from faker import Faker
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from fastapi import HTTPException
from log_config import logger
from schemas.member_schema import MemberGroup
from db.models.member import Member
from db.models.parish import Parish
from utils.member_number_generator import generate_member_no
from utils.phone_number_generator import generate_unique_phone

fake = Faker()


def check_members_exist(db: Session) -> bool:
    """
    Check if any members already exist in the database.
    """
    return db.query(Member.id).first() is not None


def create_members(db: Session, members_per_parish: int = 5):
    """
    Seed a number of members per parish.
    Args:
        db (Session): SQLAlchemy session.
        members_per_parish (int): Number of members to create for each parish.
    """
    start_time = time.time()

    parishes = db.query(Parish).all()
    if not parishes:
        logger.warning("No parishes found.")
        return

    for parish in parishes:
        parish_slug = parish.parish_data.get("parish_slug")
        if not parish_slug:
            logger.warning("Parish missing slug. Skipping.")
            continue

        existing_count = (
            db.query(func.count()).filter(Member.parish_id == parish.id).scalar()
        )
        to_create = members_per_parish - existing_count

        if to_create <= 0:
            logger.info(
                f"Parish '{parish_slug}' already has sufficient members. Skipping."
            )
            continue

        for _ in range(to_create):
            for attempt in range(5):
                first_name = fake.first_name().lower()
                last_name = fake.last_name().lower()
                email = f"{first_name}.{last_name}@{parish_slug}.iparish.co.ke"

                if (
                    db.query(Member)
                    .filter(text("member_data->>'email' = :email"))
                    .params(email=email)
                    .first()
                ):
                    logger.debug("Duplicate email encountered. Retrying.")
                    continue

                try:
                    phone = generate_unique_phone(db)
                    kin_phone = generate_unique_phone(db)
                except Exception:
                    logger.warning("Phone number generation failed. Skipping member.")
                    break

                member_data = {
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "phone": phone,
                    "residence": fake.city(),
                    "member_group": random.choice(list(MemberGroup)).value,
                    "next_of_kin_details": {
                        "first_name": fake.first_name(),
                        "last_name": fake.last_name(),
                        "email": fake.email().lower(),
                        "phone": kin_phone,
                        "residence": fake.city(),
                    },
                }

                try:
                    member_no = generate_member_no(db, parish.id)
                except HTTPException:
                    logger.warning("Failed to generate member number. Skipping member.")
                    break

                new_member = Member(
                    id=uuid.uuid4(),
                    parish_id=parish.id,
                    member_no=member_no,
                    member_data=member_data,
                    is_archived=False,
                )

                db.add(new_member)
                db.flush()
                logger.info(f"Member record added ")
                break  # success, exit retry loop

    try:
        db.commit()
        logger.info("Member seeding completed!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except Exception:
        db.rollback()
        logger.error("Database commit failed during member creation.")
        return
