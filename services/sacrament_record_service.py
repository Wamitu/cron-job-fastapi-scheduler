from decimal import Decimal
from faker import Faker
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from log_config import logger
from db.models.member import Member
from db.models.parish import Parish
from db.models.role import Role
from db.models.sacrament import Sacrament, SacramentRecord
from db.models.user import User
from faker import Faker
from utils.reference_number_generator import generate_sacrament_record_reference_number

fake = Faker()


def check_sacrament_records_requirements_exist(db: Session) -> bool:
    return db.query(Parish.id).first() and db.query(Sacrament.id).first()


def check_sacrament_records_exist(db: Session) -> bool:
    return db.query(SacramentRecord.id).first() is not None


def create_sacrament_records(db: Session):
    if not check_sacrament_records_requirements_exist(db):
        logger.warning("Missing required parishes or sacraments. Aborting.")
        return

    try:
        parishes = db.query(Parish).all()

        for parish in parishes:
            parish_id = parish.id

            sacraments = (
                db.query(Sacrament).filter(Sacrament.parish_id == parish_id).all()
            )
            if not sacraments:
                logger.warning(f"No sacraments found for parish {parish_id}!")
                continue

            # get priest for this parish
            priest = (
                db.query(User)
                .join(Role, Role.id == User.role_id)
                .filter(func.lower(Role.title) == "priest", User.parish_id == parish_id)
                .first()
            )
            if not priest:
                logger.warning(f"No priest found for parish {parish_id}! Skipping...")
                continue

            # only these sacrament names are supported for seeding
            target_sacraments = [
                "baptism",
                "marriage",
                "first communion",
                "confirmation",
            ]

            for sacrament in sacraments:
                if sacrament.name.lower() not in target_sacraments:
                    continue

                # check if record already exists
                exists_record = (
                    db.query(SacramentRecord)
                    .filter(
                        SacramentRecord.parish_id == parish_id,
                        SacramentRecord.sacrament_id == sacrament.id,
                    )
                    .first()
                )
                if exists_record:
                    logger.info(
                        f"Record for '{sacrament.name}' already exists in parish {parish_id}, skipping..."
                    )
                    continue

                if sacrament.name.lower() == "marriage":
                    data = {
                        "groomName": fake.unique.name_male(),
                        "groomDateOfBirth": fake.date_of_birth(
                            minimum_age=18, maximum_age=50
                        ).isoformat(),
                        "groomID": fake.unique.ssn(),
                        "groomPhone": fake.unique.phone_number(),
                        "groomEmail": fake.unique.email(),
                        "groomOccupation": fake.job(),
                        "groomFather": fake.name_male(),
                        "groomMother": fake.name_female(),
                        "groomAddress": fake.address(),
                        "brideName": fake.unique.name_female(),
                        "brideDateOfBirth": fake.date_of_birth(
                            minimum_age=18, maximum_age=50
                        ).isoformat(),
                        "brideID": fake.unique.ssn(),
                        "bridePhone": fake.unique.phone_number(),
                        "brideEmail": fake.unique.email(),
                        "brideOccupation": fake.job(),
                        "brideFather": fake.name_male(),
                        "brideMother": fake.name_female(),
                        "brideAddress": fake.address(),
                        "marriageDate": fake.date_this_century().isoformat(),
                        "marriageTime": fake.time(),
                        "venue": fake.company(),
                        "officiant": fake.name(),
                        "marriageType": fake.random_element(
                            elements=["civil", "sacramental"]
                        ),
                        "witness1": fake.name(),
                        "witness1ID": fake.unique.ssn(),
                        "witness2": fake.name(),
                        "witness2ID": fake.unique.ssn(),
                        "payment_status": fake.random_element(
                            elements=["paid", "pending", "not paid"]
                        ),
                        "documents": ["premarital_counseling"],
                        "notes": fake.sentence(),
                        "sacramentType": "marriage",
                        "name": f"{fake.first_name()} & {fake.first_name()}",
                        "date": fake.date_this_century().isoformat(),
                    }

                elif sacrament.name.lower() == "baptism":
                    data = {
                        "childName": fake.name(),
                        "dateOfBirth": fake.date_of_birth(
                            minimum_age=1, maximum_age=12
                        ).isoformat(),
                        "fatherName": fake.name_male(),
                        "motherName": fake.name_female(),
                        "godparent": fake.name(),
                        "baptismDate": fake.date_this_decade().isoformat(),
                        "officiant": fake.name(),
                        "venue": "St. Peter’s Parish",
                        "sacramentType": "baptism",
                        "notes": "Baptized during Sunday Mass",
                        "payment_status": "paid",
                    }

                elif sacrament.name.lower() == "first communion":
                    data = {
                        "childName": fake.name(),
                        "dateOfBirth": fake.date_of_birth(
                            minimum_age=7, maximum_age=12
                        ).isoformat(),
                        "birthPlace": fake.city(),
                        "parents": f"{fake.name_male()} & {fake.name_female()}",
                        "address": fake.address(),
                        "baptismDate": fake.date_this_decade().isoformat(),
                        "baptismParish": fake.company(),
                        "baptismCelebrant": fake.name(),
                        "preparationProgram": "CCD",
                        "classesCompleted": fake.random_int(min=1, max=8),
                        "totalClassesRequired": 8,
                        "catechist": fake.name(),
                        "preparationStartDate": fake.date_this_decade().isoformat(),
                        "communionDate": fake.date_this_decade().isoformat(),
                        "communionTime": fake.time(),
                        "venue": fake.company(),
                        "celebrant": fake.name(),
                        "communionGroup": "Group A",
                        "requirements": ["preparation_completed", "communion_attire"],
                        "specialNeeds": "",
                        "notes": "",
                        "fee": 2000,
                        "payment_status": fake.random_element(
                            elements=["not paid", "paid"]
                        ),
                        "paymentMethod": "",
                        "amountPaid": 0,
                        "sacramentType": "communion",
                        "preparationProgress": fake.random_int(min=0, max=100),
                        "name": fake.name(),
                        "date": fake.date_this_decade().isoformat(),
                        "fee_amount": 2000,
                        "outstanding_balance": 2000,
                    }

                elif sacrament.name.lower() == "confirmation":
                    data = {
                        "candidateName": fake.name(),
                        "dateOfBirth": fake.date_of_birth(
                            minimum_age=12, maximum_age=25
                        ).isoformat(),
                        "phone": fake.phone_number(),
                        "email": fake.email(),
                        "confirmationName": fake.first_name(),
                        "school": fake.company(),
                        "address": fake.address(),
                        "sponsorName": fake.name(),
                        "sponsorPhone": fake.phone_number(),
                        "sponsorRelationship": "Guardian",
                        "sponsorEmail": fake.email(),
                        "baptismDate": fake.date_this_century().isoformat(),
                        "baptismParish": fake.company(),
                        "communionDate": fake.date_this_century().isoformat(),
                        "communionParish": fake.company(),
                        "confirmationDate": fake.date_this_decade().isoformat(),
                        "confirmationTime": fake.time(),
                        "venue": fake.company(),
                        "officiant": fake.name(),
                        "notes": "Confirmation sacrament record",
                        "totalClasses": 86,
                        "classesAttended": fake.random_int(min=0, max=86),
                        "fee": 50,
                        "payment_status": fake.random_element(
                            elements=["pending", "paid"]
                        ),
                        "paymentMethod": "",
                        "amountPaid": 0,
                        "requirements": ["retreat_attended"],
                        "sacramentType": "confirmation",
                        "preparationProgress": fake.random_int(min=0, max=100),
                        "name": fake.word(),
                        "date": fake.date_this_decade().isoformat(),
                        "fee_amount": 50,
                        "outstanding_balance": 50,
                    }

                else:
                    continue

                try:
                    record = SacramentRecord(
                        reference_no=generate_sacrament_record_reference_number(
                            sacrament.name, db
                        ),
                        parish_id=parish_id,
                        sacrament_id=sacrament.id,
                        data=data,
                        generate_certificate=True,
                        fee_amount=Decimal(sacrament.fee_amount),
                        outstanding_balance=Decimal(sacrament.fee_amount),
                        created_by=priest.id,
                        is_archived=False,
                    )
                    db.add(record)
                    logger.info(f"Sacrament record for created in parish {parish_id}!")

                except Exception as e:
                    logger.error(
                        f"Failed to add record for '{sacrament.name}' in parish {parish_id}: {e.__class__.__name__}"
                    )

        # commit once after all parishes
        db.commit()
        logger.info("Sacrament record seeding completed!")

    except HTTPException as e:
        logger.warning(f"{e.status_code} | {e.detail}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Database error during sacrament seeding!: {e.__class__.__name__}"
        )
        raise

    except Exception as e:
        db.rollback()
        logger.error(
            f"Unexpected error during sacrament seeding: {e.__class__.__name__}"
        )
        raise
