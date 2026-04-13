import os
import uuid
from faker import Faker
from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from db.models.diocese import Diocese
from log_config import logger
from db.models.parish import Parish
from db.models.role import Role
from db.models.user import User
from utils.phone_number_generator import generate_unique_phone

load_dotenv()

DEFAULT_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD")
if not DEFAULT_PASSWORD:
    raise Exception("DEFAULT_USER_PASSWORD environment variable not set.")


def get_user_by_id(db: Session, id):
    if hasattr(id, "id"):
        id = id.id
    return db.query(User).filter(User.id == id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_user_details(db: Session, user_id: str):
    return get_user_by_id(db, user_id)


def check_users_exist(db: Session) -> bool:
    return db.query(User.id).first() is not None


def create_users(db: Session):
    try:
        parishes = db.query(Parish).all()
        dioceses = db.query(Diocese).all()
        roles = db.query(Role).all()

        from services.auth_service import hash_password

        if not parishes:
            raise Exception("No parishes found in the database!")
        if not dioceses:
            raise Exception("No dioceses found in the database!")
        if not roles:
            raise Exception("No roles found in the database!")

        role_map = {role.title.lower(): role for role in roles}
        fake = Faker()

        # global system admin user
        if "sysadmin" in role_map:
            sys_email = "systemadmin@iparish.co.ke"
            if not get_user_by_email(db, sys_email):
                db.add(
                    User(
                        id=uuid.uuid4(),
                        first_name="System",
                        last_name="Admin",
                        email=sys_email,
                        phone=generate_unique_phone(db),
                        hashed_password=hash_password(DEFAULT_PASSWORD),
                        diocese_id=None,
                        parish_id=None,
                        role_id=role_map["sysadmin"].id,
                        is_active=True,
                        is_archived=False,
                    )
                )
                logger.info("Global SysAdmin created!")
        else:
            logger.warning("SysAdmin role not found!")

        # global finance user
        if "finance" in role_map:
            fin_email = "financeadmin@iparish.co.ke"
            if not get_user_by_email(db, fin_email):
                db.add(
                    User(
                        id=uuid.uuid4(),
                        first_name="Finance",
                        last_name="Admin",
                        email=fin_email,
                        phone=generate_unique_phone(db),
                        hashed_password=hash_password(DEFAULT_PASSWORD),
                        diocese_id=None,
                        parish_id=None,
                        role_id=role_map["finance"].id,
                        is_active=True,
                        is_archived=False,
                    )
                )
                logger.info("Global Finance Admin created!")
        else:
            logger.warning("Finance role not found!")

        # bishop for each diocese (deterministic names/emails, ensure diocese_id set)
        if "bishop" in role_map:
            for diocese in dioceses:
                diocese_name = diocese.name.lower()
                if not diocese_name:
                    logger.warning(f"Diocese has no name. Skipping bishop creation.")
                    continue

                # Deterministic slug from diocese name
                diocese_slug = "".join(ch for ch in diocese_name if ch.isalnum())
                email = f"bishop@{diocese_slug}.iparish.co.ke"
                first_name = "Bishop"
                last_name = diocese.name.replace(" ", "")[:30]

                if not get_user_by_email(db, email):
                    db.add(
                        User(
                            id=uuid.uuid4(),
                            first_name=first_name,
                            last_name=last_name,
                            email=email,
                            phone=generate_unique_phone(db),
                            hashed_password=hash_password(DEFAULT_PASSWORD),
                            diocese_id=diocese.id,
                            parish_id=None,
                            role_id=role_map["bishop"].id,
                            is_active=True,
                            is_archived=False,
                        )
                    )
                    logger.info(f"Bishop created for {diocese_name} diocese!")
        else:
            logger.warning("Bishop role not found!")

        # parish-specific users
        for parish in parishes:
            slug = parish.parish_data.get("parish_slug", "").lower()
            if not slug:
                logger.warning("Parish has no slug! Skipping...")
                continue

            for role_title, role in role_map.items():
                if role_title in ["sysadmin", "finance", "bishop"]:
                    continue  # skip global/parish/diocese roles

                # One Priest per parish
                if role_title == "priest":
                    # Deterministic parish priest user
                    email = f"priest@{slug}.iparish.co.ke"
                    first_name = "priest"
                    last_name = parish.parish_data.get("parish_name", "Parish")[:30]
                    if not get_user_by_email(db, email):
                        db.add(
                            User(
                                id=uuid.uuid4(),
                                first_name=first_name,
                                last_name=last_name,
                                email=email,
                                phone=generate_unique_phone(db),
                                hashed_password=hash_password(DEFAULT_PASSWORD),
                                diocese_id=parish.diocese_id,
                                parish_id=parish.id,
                                role_id=role.id,
                                is_active=True,
                                is_archived=False,
                            )
                        )
                        logger.info(f"Priest created for parish {slug}!")
                else:
                    # One user for each remaining role per parish (deterministic)
                    email = f"{role_title}@{slug}.iparish.co.ke"
                    first_name = role.title.capitalize()
                    last_name = parish.parish_data.get("parish_name", "Parish")[:30]
                    if not get_user_by_email(db, email):
                        db.add(
                            User(
                                id=uuid.uuid4(),
                                first_name=first_name,
                                last_name=last_name,
                                email=email,
                                phone=generate_unique_phone(db),
                                hashed_password=hash_password(DEFAULT_PASSWORD),
                                diocese_id=parish.diocese_id,
                                parish_id=parish.id,
                                role_id=role.id,
                                is_active=True,
                                is_archived=False,
                            )
                        )
                        logger.info(f"{role.title} created for parish {slug}!")

        db.commit()
        logger.info("User seeding completed successfully!")

    except HTTPException as e:
        db.rollback()
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during user seeding: {str(e)}")
        raise

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during user seeding: {str(e)}")
        raise
