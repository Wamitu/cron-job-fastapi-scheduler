from fastapi import APIRouter, Depends, HTTPException
from core.tasks import send_bulk_sms_task
from db.models.user import User
from db.session import get_db
from sqlalchemy.orm import Session
from schemas.bulk_communication_schema import BulkInviteRequest
from utils.bulk_email_client import send_bulk_invites

router = APIRouter()


@router.post("/send-sms/")
def send_sms_endpoint(
    message: str, recipients: list[str], masked_number: str = None, telco: str = None
):
    task = send_bulk_sms_task.delay(message, recipients, masked_number, telco)
    return {"task_id": task.id, "status": "queued"}


@router.post("/send-bulk-emails", summary="Send bulk emails to users")
def send_bulk_invites_endpoint(
    request: BulkInviteRequest, db: Session = Depends(get_db)
):
    users = db.query(User).filter(User.id.in_(request.user_ids)).all()
    if not users:
        raise HTTPException(status_code=404, detail="No users found for provided IDs")

    # Convert users into Invitee objects
    # invitees = []
    # for user in users:
    #     invitees.append(
    #         Invitee(
    #             first_name=user.first_name,
    #             last_name=user.last_name,
    #             token=user.invite_token,  # assume you store token
    #             email=user.email,
    #             parish_name=request.parish_name,
    #         )
    #     )

    # send_bulk_invites(invitees)
    # return {"message": f"Invitations sent to {len(invitees)} users."}
