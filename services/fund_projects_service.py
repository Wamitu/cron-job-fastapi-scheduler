from random import randint
import uuid
from log_config import logger
from decimal import Decimal
from faker import Faker
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from db.models.parish import Parish
from db.models.fund_project import FundProject
from schemas.fund_project_schema import FundProjectStatus
from utils.account_suffix_generator import generate_account_suffix

fake = Faker()

# Predefined Catholic fund themes
FUND_TOPICS = [
    "Church Renovation",
    "Sanctuary Construction",
    "Youth Catechism",
    "Parish Hall Upgrade",
    "St. Vincent De Paul Fund",
    "Rosary Group Support",
    "Altar Server Training",
    "Health Mission Outreach",
    "Sacristy Expansion",
    "Community Feeding Program",
    "Catholic Education Sponsorship",
    "New Roof Project",
    "Cemetery Fencing",
    "Chapel Lighting",
    "School Bursary Support",
    "Missionary Fund",
]


def check_fund_projects_exist(db: Session) -> bool:
    """
    Check whether any fund projects already exist in the database.
    Returns:
        bool: True if at least one fund project exists, else False.
    """
    return db.query(FundProject.id).first() is not None


def create_fund_projects(db: Session, projects_per_parish: int = 5):
    parishes = db.query(Parish).all()
    if not parishes:
        logger.warning("No parishes found!")
        return

    # Global tracker of all fund names used
    used_names_global = set(name for name, in db.query(FundProject.name).all())

    for parish in parishes:
        parish_id = parish.id
        parish_name = parish.parish_data.get("parish_name", "Unknown")
        logger.info(f"Seeding fund projects for parish: {parish_name}")

        # Track per-parish usage
        existing_names = set(
            name
            for name, in db.query(FundProject.name)
            .filter(FundProject.parish_id == parish_id)
            .all()
        )
        existing_suffixes = set(
            suffix
            for suffix, in db.query(FundProject.account_suffix)
            .filter(FundProject.parish_id == parish_id)
            .all()
        )

        created_count = 0
        attempts = 0
        max_attempts = projects_per_parish * 4

        status_cycle = [
            FundProjectStatus.active,
            FundProjectStatus.inactive,
            FundProjectStatus.completed,
        ]

        name_counters = {}

        while created_count < projects_per_parish and attempts < max_attempts:
            attempts += 1
            base_name = fake.random_element(tuple(FUND_TOPICS))
            unique_suffix = fake.unique.word().capitalize()
            name = f"{base_name} - {unique_suffix}"

            if name in existing_names:
                logger.warning("Duplicate project name found! Skipping...")
                continue

            account_suffix = generate_account_suffix(base_name, parish_id, db)
            if account_suffix in existing_suffixes:
                logger.warning("Duplicate account suffix found! Skipping...")
                continue

            description = f"This is a fund project for {base_name.lower()} in {parish_name} parish."
            target_amount = Decimal("10000.00")
            status = status_cycle[created_count % len(status_cycle)]

            current_amount = (
                target_amount + Decimal(randint(100, 1000))
                if status == FundProjectStatus.completed
                else Decimal("0.00")
            )

            try:
                project = FundProject(
                    id=uuid.uuid4(),
                    parish_id=parish_id,
                    name=name,
                    description=description,
                    account_suffix=account_suffix,
                    status=status,
                    target_amount=target_amount,
                    current_amount=current_amount,
                    is_archived=False,
                )

                db.add(project)
                db.flush()
                created_count += 1
                existing_names.add(name)
                used_names_global.add(name)
                existing_suffixes.add(account_suffix)

                logger.info(f"Created fund project successfully!")

            except SQLAlchemyError as e:
                logger.error(
                    "Database error while creating fund project!: %s",
                    e.__class__.__name__,
                )
                db.rollback()

    try:
        db.commit()
        logger.info("Fund project seeding completed successfully.")
    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during fund project data seeding!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")
    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during fund project data seeding!", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")
