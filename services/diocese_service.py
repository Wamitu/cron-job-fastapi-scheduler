from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import exists, func
from db.models.diocese import Diocese
from log_config import logger


def check_dioceses_exist(db: Session) -> bool:
    """
    Check if at least one diocese exists in the database.
    """
    return db.query(Diocese.id).first() is not None


def create_dioceses(db: Session):
    """
    Seed predefined dioceses into the database if they do not already exist.
    """
    diocese_data = [
        {"name": "Nairobi", "description": "Diocese of Nairobi."},
        {"name": "Mombasa", "description": "Diocesan Mombasa."},
        {"name": "Meru", "description": "Diocese of Meru."},
        {"name": "Machakos", "description": "Diocese of Machakos."},
        {"name": "Nyeri", "description": "Diocese of Nyeri."},
        {"name": "Muranga", "description": "Diocese of Muranga."},
        {"name": "Kisumu", "description": "Diocese of Kisumu."},
    ]

    created = 0
    skipped = 0

    try:
        for diocese_info in diocese_data:
            name = diocese_info["name"]
            exists_query = db.query(
                exists().where(func.lower(Diocese.name) == name.lower())
            ).scalar()
            if not exists_query:
                db.add(
                    Diocese(
                        **diocese_info,
                    )
                )
                created += 1
            else:
                skipped += 1

        db.commit()
        logger.info(
            "Diocese seeding complete. %d dioceses created, %d skipped.",
            created,
            skipped,
        )

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during diocese creation: %s", e.__class__.__name__)
        raise
