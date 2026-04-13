from slugify import slugify
from sqlalchemy import String, cast
from sqlalchemy.orm import Session
from db.models.parish import Parish
from log_config import logger

def generate_unique_slug(name: str, db: Session) -> str:
    """
    Generate a unique slug for a parish based on the provided name.

    The function ensures the slug does not already exist in the parish_data JSON field
    under the 'parish_slug' key. If the slug exists, a numeric suffix is appended
    (e.g., 'st-marys', 'st-marys-1', 'st-marys-2', etc.).

    Args:
        name (str): The base name to generate the slug from (e.g., "St Mary's Parish").
        db (Session): SQLAlchemy database session used to check for existing slugs.

    Returns:
        str: A unique slug string.
    """
    # Convert the name into a URL-safe slug (e.g. "St Mary's Parish" -> "st-marys-parish")
    base_slug = slugify(name)
    slug = base_slug
    count = 1

    logger.debug("Starting slug generation process.")

    # Loop until a unique slug is found
    while db.query(Parish).filter(
        cast(Parish.parish_data["parish_slug"], String) == slug
    ).first():
        logger.debug("Slug already exists, retrying with increment.")
        slug = f"{base_slug}-{count}"
        count += 1

    logger.info("Unique slug generated successfully.")
    return slug
