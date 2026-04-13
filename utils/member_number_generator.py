import random
import re
import string
from uuid import UUID
from fastapi import HTTPException
from requests import Session
from db.models.member import Member
from db.models.parish import Parish
from log_config import logger


# generate a unique member number for a parish
def generate_member_no(db: Session, parish_id):
    """
    Generates a new member number based on the parish's prefix and current members.

    Format: <PREFIX>-<SEQUENTIAL_SUFFIX>
    e.g., "ABC-001"

    Args:
        db (Session): SQLAlchemy session
        parish_id (UUID): The parish's ID

    Returns:
        str: The generated member number

    Raises:
        HTTPException: If the parish doesn't exist or lacks prefix/suffix configuration
    """
    # Retrieve the parish record
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        logger.warning("Parish not found while generating member number.")
        raise HTTPException(status_code=404, detail="Parish not found.")

    prefix = parish.member_number_prefix
    start_suffix = parish.member_number_suffix

    # Ensure the parish has a valid prefix and suffix
    if not prefix or not start_suffix:
        logger.error("Missing prefix/suffix in parish settings.")
        raise HTTPException(
            status_code=400, detail="Missing prefix/suffix in parish settings."
        )

    # Fetch all existing member numbers for the parish
    members = db.query(Member.member_no).filter(Member.parish_id == parish_id).all()
    suffixes = []

    # Extract numeric suffix from existing member numbers
    for (member_no,) in members:
        match = re.match(rf"^{prefix}-(\d+)$", member_no)
        if match:
            suffixes.append(int(match.group(1)))

    # Determine the next suffix to assign
    next_suffix = max(suffixes) + 1 if suffixes else int(start_suffix)
    padded_suffix = str(next_suffix).zfill(len(start_suffix))  # Keep consistent length

    logger.info("Member number generated successfully.")
    return f"{prefix}-{padded_suffix}"


# generate suggested 3-letter prefixes for new parishes
def generate_member_number_prefix_suggestions(db: Session, count: int = 5):
    """
    Generate a list of random 3-letter prefixes that don't currently exist in the system.

    Args:
        db (Session): SQLAlchemy session
        count (int): Number of suggestions to return

    Returns:
        List[str]: A list of unique 3-letter prefixes
    """
    # Get all existing prefixes from the database
    existing = set(prefix[0] for prefix in db.query(Parish.member_number_prefix).all())

    suggestions = set()
    attempts = 0
    logger.debug("Generating prefix suggestions for parish member numbers.")

    # Try generating new unique 3-letter combinations
    while len(suggestions) < count and attempts < 100:
        suggestion = "".join(random.choices(string.ascii_uppercase, k=3))
        if suggestion not in existing:
            suggestions.add(suggestion)
        attempts += 1

    logger.info("Prefix suggestions generated.")
    return list(suggestions)


# reassign member numbers after prefix/suffix change
def update_member_numbers(parish_id: UUID, db: Session):
    """
    Recalculate and update all member numbers for a given parish,
    starting from the configured suffix.

    Format remains <PREFIX>-<SEQUENTIAL_SUFFIX>

    Args:
        parish_id (UUID): ID of the parish
        db (Session): SQLAlchemy session

    Raises:
        ValueError: If parish is not found or suffix is not numeric
    """
    # Fetch parish record
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        logger.error("Parish not found while updating member numbers.")
        raise ValueError("Parish not found.")

    prefix = parish.member_number_prefix

    # Ensure the suffix is numeric
    try:
        start_suffix = int(parish.member_number_suffix)
    except ValueError:
        logger.error("Invalid suffix: must be numeric.")
        raise ValueError("member_number_suffix must be numeric.")

    # Get members sorted by creation time for consistent numbering
    members = (
        db.query(Member)
        .filter(Member.parish_id == parish_id)
        .order_by(Member.created_at.asc())
        .all()
    )

    # Assign sequential numbers to members
    for index, member in enumerate(members):
        new_suffix = start_suffix + index
        padded_suffix = str(new_suffix).zfill(3)
        member.member_no = f"{prefix}-{padded_suffix}"

    db.commit()
    logger.info("Member numbers updated successfully.")
