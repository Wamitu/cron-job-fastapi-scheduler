import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import exists, func
from db.models.role import Role
from log_config import logger


def check_roles_exist(db: Session) -> bool:
    """
    Check if at least one role exists in the database.
    """
    return db.query(Role.id).first() is not None


def create_roles(db: Session):
    """
    Seed predefined roles into the database if they do not already exist.
    """
    role_data = [
        {"title": "SysAdmin", "description": "System administrator role."},
        {"title": "Bishop", "description": "Diocesan leader role."},
        {"title": "Priest", "description": "Parish priest role."},
        {"title": "Finance", "description": "Finance handler role."},
        {"title": "ParishAdmin", "description": "Parish admin role."},
        {"title": "ChurchSecretary", "description": "Secretary support role."},
        {"title": "PastoralCouncilMember", "description": "Advisory council role."},
    ]

    created = 0
    skipped = 0

    try:
        for role_info in role_data:
            title = role_info["title"]
            exists_query = db.query(
                exists().where(func.lower(Role.title) == title.lower())
            ).scalar()
            if not exists_query:
                db.add(
                    Role(
                        **role_info,
                        is_archived=False,
                    )
                )
                created += 1
            else:
                skipped += 1

        db.commit()
        logger.info(
            "Role seeding complete. %d roles created, %d skipped.", created, skipped
        )

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Database error during role creation: %s", e.__class__.__name__)
        raise
