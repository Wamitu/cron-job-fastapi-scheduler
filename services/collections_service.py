import logging
import random
import time
from decimal import Decimal
from uuid import uuid4
from faker import Faker
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from log_config import logger
from db.models.collection import Collection
from db.models.fund_project import FundProject
from db.models.member import Member
from db.models.parish import Parish
from db.models.user import User
from schemas.collection_schema import CollectionMethod, CollectionType

fake = Faker()


def check_collections_exist(db: Session) -> bool:
    """
    Check if any collection records exist in the database.
    """
    return db.query(Collection.id).first() is not None


def create_collections(db: Session, count_per_parish: int = 5):
    """
    Seed random collections for each parish with associated members and optional fund projects.

    Args:
        db (Session): SQLAlchemy DB session.
        count_per_parish (int): Number of collections to create per parish.
    """
    start_time = time.time()

    try:
        parishes = db.query(Parish).all()
        members = db.query(Member).all()
        projects = db.query(FundProject).all()
        users = db.query(User).all()

        if not parishes:
            logger.warning(
                "No parishes found in database. Aborting collection seeding!"
            )
            return
        if not members:
            logger.warning("No members found in database. Aborting collection seeding!")
            return
        if not users:
            logger.warning("No users found in database. Aborting collection seeding!")
            return

        project_ids = [p.id for p in projects]
        user_ids = [u.id for u in users]
        total_created = 0

        for parish in parishes:
            parish_members = [m for m in members if m.parish_id == parish.id]
            if not parish_members:
                logger.warning("No members for parish. Skipping...")
                continue

            for _ in range(count_per_parish):
                member = random.choice(parish_members)
                recorded_by_user = random.choice(users)

                try:
                    collection = Collection(
                        id=uuid4(),
                        collection_type=random.choice(list(CollectionType)),
                        member_id=member.id,
                        parish_id=parish.id,
                        project_id=(
                            random.choice(project_ids)
                            if project_ids and random.choice([True, False])
                            else None
                        ),
                        sacrament_record_id=None,
                        collection_method=random.choice(list(CollectionMethod)),
                        collection_data={
                            "transaction_ref": fake.bothify("TXN#######"),
                            "payment_gateway": random.choice(["Mpesa", "Cash", "Card"]),
                        },
                        contributor_data=None,
                        recorded_by=recorded_by_user.id,
                        amount=Decimal(random.randint(100, 10000)),
                        is_archived=False,
                    )

                    db.add(collection)
                    total_created += 1
                    logger.info("Collection created in parish for member!")

                except SQLAlchemyError as e:
                    logger.error("Database error while creating collection for parish!")
                    db.rollback()

        db.commit()
        duration = round(time.time() - start_time, 2)
        logger.info("Collection seeding completed!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}", exc_info=True)
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "500 | Database error during collection data seeding!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="A database error occurred!")

    except Exception:
        db.rollback()
        logger.error(
            "500 | Unexpected error during colelction data seeding!",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred!")
