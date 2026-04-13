import hashlib
import random
import string
import time
from fastapi import Depends
from db.models.certificate import Certificate
from db.session import get_db
import uuid
from sqlalchemy.orm import Session
from db.session import SessionLocal
from db.models.sacrament import SacramentRecord
from db.models.user import User
from log_config import logger


def generate_certificate_number(prefix: str = "CERT") -> str:
    """
    Generates a unique certificate number using a prefix, timestamp, random string, and hash.
    Format: PREFIX-YYYYMMDDHHMMSS-RANDOM-HASH
    Example: CERT-20250616123530-X7L9P2-A1B2C3D4
    """
    timestamp = time.strftime("%Y%m%d%H%M%S")  # e.g. 20250616123530
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    raw = f"{prefix}-{timestamp}-{random_part}"
    hash_part = hashlib.sha256(raw.encode()).hexdigest()[:8].upper()
    return f"{prefix}-{timestamp}-{random_part}-{hash_part}"


def generate_unique_certificate_number(db=Depends(get_db), prefix: str = "CERT") -> str:
    cert_number = generate_certificate_number(prefix)
    existing_cert_number = (
        db.query(Certificate).filter(Certificate.certificate_no == cert_number).first()
    )
    if not existing_cert_number:
        return cert_number
    raise Exception(
        "Unable to generate a unique certificate number after multiple attempts!"
    )


def check_certificates_exist(db: Session) -> bool:
    """
    Check if any certificates already exist in the database.
    Returns True if at least one certificate exists, otherwise False.
    """
    return db.query(Certificate.id).first() is not None


def create_certificates(db: Session):
    db: Session = SessionLocal()

    try:
        # Get sacrament records that need certificates
        sacrament_records = (
            db.query(SacramentRecord)
            .filter(
                SacramentRecord.generate_certificate == True,
                SacramentRecord.is_archived == False,
            )
            .all()
        )

        for record in sacrament_records:
            sacrament_record_sacrament_name = record.sacrament.name

            certificate_for = None

            name_lower = sacrament_record_sacrament_name.lower()

            if name_lower == "baptism":
                certificate_for = record.data.get("childName")
            elif name_lower == "confirmation":
                certificate_for = record.data.get("candidateName")
            elif name_lower == "marriage":
                groom = record.data.get("groomName")
                bride = record.data.get("brideName")
                if groom and bride:
                    certificate_for = f"{groom} & {bride}"
                else:
                    certificate_for = groom or bride
            elif name_lower == "first communion":
                certificate_for = record.data.get("childName")

            else:
                certificate_for = "Unknown"

            # Get a user from the same parish
            user = db.query(User).filter(User.parish_id == record.parish_id).first()
            if not user:
                continue

            # Check if a certificate already exists for this record
            exists = (
                db.query(Certificate)
                .filter(Certificate.sacrament_record_id == record.id)
                .first()
            )
            if exists:
                continue

            # Create certificate
            certificate = Certificate(
                id=uuid.uuid4(),
                parish_id=record.parish_id,
                sacrament_record_id=record.id,
                certificate_for=certificate_for,
                certificate_no=generate_unique_certificate_number(db),
                generated_by=user.id,
                is_archived=False,
            )

            db.add(certificate)

        db.commit()
        logger.info("Certificate seeding completed!")

    except Exception as e:
        db.rollback()
        logger.info("Error seeding certificates: {e}")

    finally:
        db.close()
