import logging
from log_config import logger
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import exists, and_
from db.models.parish import Parish
from db.models.sacrament import Sacrament


def check_sacraments_exist(db: Session) -> bool:
    return db.query(Sacrament.id).first() is not None


def create_sacraments(db: Session):
    sacrament_data = [
        {"name": "Baptism", "rules": [], "fee_amount": 250.00},
        {"name": "Marriage", "rules": [], "fee_amount": 500.00},
        {"name": "Confirmation", "rules": [], "fee_amount": 750.00},
        {"name": "First Communion", "rules": [], "fee_amount": 1000.00},
    ]

    try:
        parishes = db.query(Parish).all()
        if not parishes:
            logger.warning("No parishes found! Aborting sacrament seeding.")
            return

        for parish in parishes:
            added, skipped = 0, 0

            for sacrament_info in sacrament_data:
                already_exists = db.query(
                    exists().where(
                        and_(
                            Sacrament.name == sacrament_info["name"],
                            Sacrament.parish_id == parish.id,
                        )
                    )
                ).scalar()

                if already_exists:
                    skipped += 1
                    continue

                try:
                    new_sacrament = Sacrament(
                        parish_id=parish.id,
                        name=sacrament_info["name"],
                        rules=sacrament_info["rules"],
                        fee_amount=sacrament_info["fee_amount"],
                        is_archived=False,
                    )
                    db.add(new_sacrament)
                    added += 1
                except SQLAlchemyError:
                    logger.warning(f"Error adding sacrament to parish! Skipping...")
                    continue

            logger.info(f"Created sacrament records for parish successfully!")

        db.commit()
        logger.info("Sacrament seeding completed!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError:
        db.rollback()
        logger.error("Database error during sacrament seeding!")
        raise

    except Exception:
        db.rollback()
        logger.error("Unexpected error during sacrament seeding.")
        raise
