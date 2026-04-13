from sqlalchemy.orm import Session
from db.models.receipt import Receipt


def generate_receipt_number(db: Session, parish_id: str) -> str:
    """
    Auto-generate a sequential receipt number for a given parish.
    Format: 6-digit padded number (e.g., 000001, 000002).
    """

    # Get the latest receipt for this parish
    last_receipt = (
        db.query(Receipt)
        .filter(Receipt.parish_id == parish_id)
        .order_by(Receipt.created_at.desc())
        .first()
    )

    if last_receipt and last_receipt.receipt_no.isdigit():
        next_number = int(last_receipt.receipt_no) + 1
    else:
        next_number = 1

    # Return a zero-padded 6-digit number
    return f"{next_number:06d}"
