import re
from sqlalchemy.orm import Session
from db.models.fund_project import FundProject
from log_config import logger


def generate_account_suffix(name: str, parish_id, db: Session) -> str:
    """
    Generate a unique account suffix for a fund project name, scoped to a parish.

    The suffix is derived from the project name, sanitized to be URL-safe,
    and made unique by appending a counter if necessary. Ensures uniqueness
    per parish without logging or exposing the generated value.
    """
    suffix = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
    base_suffix = suffix[:20]
    counter = 1

    while (
        db.query(FundProject)
        .filter_by(parish_id=parish_id, account_suffix=suffix)
        .first()
    ):
        suffix = f"{base_suffix}_{counter}"
        counter += 1

    logger.info("Generated unique account suffix for fund project.")
    return suffix
