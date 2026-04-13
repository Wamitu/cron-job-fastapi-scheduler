from datetime import datetime
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from uuid import UUID
from api.serializers import (
    serialize_subscription_payments,
)
from db.models.receipt import Receipt
from db.models.user import User
from db.session import get_db
from db.models.parish_subscription import (
    ParishSubscription,
)
from sqlalchemy.orm import joinedload
from dateutil.relativedelta import relativedelta
from db.models.subscription_plan import SubscriptionPlan
from db.models.parish_subscription import SubscriptionPayment
from schemas.parish_subscription_schema import (
    PaginatedSubscriptionPaymentResponse,
    SubscriptionPaymentCreate,
    SubscriptionPaymentDetails,
)
from log_config import logger
from services.auth_service import get_current_user
from services.user_service import get_user_details
from utils.receipt_no_generator import generate_receipt_number

router = APIRouter()


# Retrieve all subscription payments
@router.get(
    "/all",
    response_model=PaginatedSubscriptionPaymentResponse,
    summary="Get all parish subscription payments",
)
def get_all_subscription_payments(
    parish_id: Optional[UUID] = Query(None, description="Filter by parish ID"),
    is_archived: Optional[bool] = None,
    paid_from: Optional[datetime] = Query(
        None, description="Filter by start of paid_at date"
    ),
    paid_to: Optional[datetime] = Query(
        None, description="Filter by end of paid_at date"
    ),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
):
    query = (
        db.query(SubscriptionPayment)
        .join(SubscriptionPayment.parish_subscription)
        .options(
            joinedload(SubscriptionPayment.parish_subscription).joinedload(
                ParishSubscription.parish
            )
        )
    )

    if is_archived is None:
        query = query.filter(SubscriptionPayment.is_archived == False)
    else:
        query = query.filter(SubscriptionPayment.is_archived == is_archived)

    if parish_id:
        query = query.filter(ParishSubscription.parish_id == parish_id)

    if paid_from:
        query = query.filter(SubscriptionPayment.paid_at >= paid_from)

    if paid_to:
        query = query.filter(SubscriptionPayment.paid_at <= paid_to)

    # search parameter
    if search:
        query = query.filter(
            or_(
                SubscriptionPayment.created_at.ilike(f"%{search}%"),
                SubscriptionPayment.paid_at.ilike(f"%{search}%"),
                SubscriptionPayment.amount.ilike(f"%{search}%"),
            )
        )

    # sort parameter
    if sort_by:
        if hasattr(SubscriptionPayment, sort_by):
            sort_column = getattr(SubscriptionPayment, sort_by)
            query = query.order_by(
                sort_column.desc() if sort_order == "desc" else sort_column.asc()
            )
        else:
            logger.warning("400 | Invalid sort_by field!")
            raise HTTPException(status_code=400, detail="Invalid sort_by field!")

    offset = (page - 1) * page_size

    total_count = query.count()
    payments = query.offset(offset).limit(page_size).all()

    if not payments:
        raise HTTPException(status_code=404, detail="No subscription payments found!")

    return {
        "items": serialize_subscription_payments(payments),
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "pages": (total_count + page_size - 1) // page_size,
    }

    return results


# Make subscription payment
@router.post(
    "/create",
    response_model=SubscriptionPaymentDetails,
)
def record_subscription_payment(
    data: SubscriptionPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    logger.info("Recording subscription payment...")

    # Load subscription with related parish
    subscription = (
        db.query(ParishSubscription)
        .options(joinedload(ParishSubscription.parish))
        .filter(ParishSubscription.id == data.parish_subscription_id)
        .first()
    )

    if not subscription:
        logger.info("404 | Subscription not found!")
        raise HTTPException(status_code=404, detail="Parish subscription not found!")

    if subscription.status == "active":
        logger.info("400 | Cannot make a payment for an already active subscription!")
        raise HTTPException(
            status_code=400,
            detail="This subscription is already active and fully paid!",
        )

    # Check if any payment exists
    existing_payment = (
        db.query(SubscriptionPayment)
        .filter(
            SubscriptionPayment.parish_subscription_id == data.parish_subscription_id
        )
        .first()
    )

    if existing_payment:
        logger.info("400 | Partial or prior payment already exists!")
        raise HTTPException(
            status_code=400,
            detail="A payment has already been recorded for this subscription!",
        )

    plan = db.get(SubscriptionPlan, subscription.subscription_plan_id)
    if not plan:
        logger.info("404 | Subscription plan not found!")
        raise HTTPException(status_code=404, detail="Subscription plan not found!")

    try:
        amount = Decimal(str(data.amount))
    except Exception:
        logger.error(f"Invalid amount: {data.amount}")
        raise HTTPException(status_code=400, detail="Invalid amount format.")

    if amount != plan.price:
        logger.info("400 | Payment amount does not match the subscription plan price.")
        raise HTTPException(
            status_code=400,
            detail=f"Payment must match the subscription price exactly: {plan.price}",
        )

    # Record payment
    payment = SubscriptionPayment(
        parish_subscription_id=data.parish_subscription_id,
        amount=amount,
        channel=data.channel,
        reference=data.reference,
        paid_at=data.paid_at,
        recorded_by=user.id,
        created_at=datetime.utcnow(),
    )

    db.add(payment)

    # Activate the subscription
    subscription.is_paid = True
    subscription.status = "active"
    subscription.payment_reference = payment.reference
    now = datetime.utcnow()
    subscription.start_date = now
    subscription.end_date = now + relativedelta(months=1)

    db.flush()

    receipt_no = generate_receipt_number(db, subscription.parish_id)

    # Create receipt
    new_receipt = Receipt(
        parish_id=subscription.parish_id,
        collection_id=None,
        subscription_payment_id=payment.id,
        receipt_no=receipt_no,
        generated_by=user.id,
    )
    db.add(new_receipt)

    # Commit everything
    db.commit()
    db.refresh(payment)
    db.refresh(new_receipt)

    logger.info("Payment recorded and subscription activated successfully.")

    # return response with parish attached
    return payment


# Retrieve payment details
@router.get(
    "/payment/{payment_id}/details",
    response_model=SubscriptionPaymentDetails,
    summary="Get details of a specific subscription payment by ID",
)
def get_subscription_payment_by_id(
    payment_id: UUID = Path(..., description="The ID of the subscription payment"),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(SubscriptionPayment)
        .join(SubscriptionPayment.parish_subscription)
        .options(
            joinedload(SubscriptionPayment.parish_subscription).joinedload(
                ParishSubscription.parish
            )
        )
        .filter(SubscriptionPayment.id == payment_id)
        .first()
    )

    if not payment:
        raise HTTPException(status_code=404, detail="Subscription payment not found")

    result_data = payment.__dict__.copy()
    result_data["parish"] = payment.parish_subscription.parish

    return SubscriptionPaymentDetails(**result_data)


# archive subscription payment
@router.post(
    "/payment/archive/{subscription_payment_id}",
    summary="Archive subscription payment",
)
async def archive_subscription_payment(
    subscription_payment_id: UUID,
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to archive subscription payment...")
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    role_title = user.role.title if hasattr(user.role, "title") else None

    # parish existence check
    if parish_id is not None:
        parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

    # role and parish based check
    if role_title == "Priest":
        if parish_id is None:
            raise HTTPException(
                status_code=403,
                detail="Priests must specify a parish_id to archive subscription payment data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to archive subscription payment data from another parish.",
            )

    subscription_payment = (
        db.query(SubscriptionPayment)
        .filter(SubscriptionPayment.id == subscription_payment_id)
        .first()
    )

    if not subscription_payment:
        raise HTTPException(status_code=404, detail="Subscription payment not found!")

    # Archive it
    subscription_payment.is_archived = True
    db.add(subscription_payment)
    db.commit()
    db.refresh(subscription_payment)

    return {"message": "Subscription payment successfully archived!"}


# unarchive subscription payment
@router.post(
    "/payment/unarchive/{subscription_payment_id}",
    summary="Unarchive subscription payment",
)
async def unarchive_subscription_payment(
    subscription_payment_id: UUID,
    db: Session = Depends(get_db),
    parish_id: Optional[UUID] = Query(None, description="Optional parish ID filter"),
    current_user: User = Depends(get_current_user),
):
    logger.info("Attempting to unarchive subscription payment...")
    user = get_user_details(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    role_title = user.role.title if hasattr(user.role, "title") else None

    # parish existence check
    if parish_id is not None:
        parish = db.query(Parish).filter(Parish.id == parish_id).first()
        if not parish:
            logger.warning("404 | Parish not found!")
            raise HTTPException(status_code=404, detail="Parish not found!")

    # role and parish based check
    if role_title == "Priest":
        if parish_id is None:
            raise HTTPException(
                status_code=403,
                detail="Priests must specify a parish_id to unarchive subscription payment data.",
            )

        if parish_id != user.parish_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to unarchive subscription payment data from another parish.",
            )

    subscription_payment = (
        db.query(SubscriptionPayment)
        .filter(SubscriptionPayment.id == subscription_payment_id)
        .first()
    )

    if not subscription_payment:
        raise HTTPException(status_code=404, detail="Subscription payment not found!")

    # Unarchive it
    subscription_payment.is_archived = False
    db.add(subscription_payment)
    db.commit()
    db.refresh(subscription_payment)

    return {"message": "Subscription payment successfully unarchived!"}
