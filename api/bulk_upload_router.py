import io
import csv
import json
import re
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Query, UploadFile, File, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func
from sqlalchemy.orm import Session
from typing import List, Optional
from db.models.certificate import Certificate
from db.models.collection import Collection
from db.models.fund_project import FundProject
from db.models.member import Member
from db.models.parish import Parish
from db.models.role import Role
from db.models.sacrament import Sacrament, SacramentRecord
from schemas.collection_schema import CollectionType, CollectionMethod
from db.session import get_db
from db.models.attendance import Attendance
from db.models.user import User
from schemas.member_schema import (
    MemberCreate,
    MemberData,
    MemberGroup,
    NextOfKinDetails,
)
from services.auth_service import get_current_user, hash_password
from services.notification_service import create_notification
from schemas.notification_schema import NotificationType
from log_config import logger
from services.certificate_service import generate_unique_certificate_number
from utils.account_suffix_generator import generate_account_suffix
from utils.member_number_generator import generate_member_no
from utils.parish_slug_generator import generate_unique_slug
from utils.reference_number_generator import generate_sacrament_record_reference_number

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _err(row: int, column: str, value: str, message: str) -> dict:
    return {"row": row, "column": column, "value": value, "message": message}


def _require(errors: list, row: int, column: str, value: str) -> bool:
    """Append error if value is blank. Returns True if valid."""
    if not value:
        errors.append(_err(row, column, value, "This field is required"))
        return False
    return True


def _require_email(errors: list, row: int, column: str, value: str):
    if _require(errors, row, column, value):
        if not EMAIL_RE.match(value):
            errors.append(_err(row, column, value, "Invalid email format"))


_ACCEPTED_DATE_FMTS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
]


def _parse_date(value: str) -> str | None:
    """Return value normalized to YYYY-MM-DD, or None if unparseable."""
    for fmt in _ACCEPTED_DATE_FMTS:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _require_date(errors: list, row: int, column: str, value: str) -> str | None:
    """Validate and normalize a date field. Returns normalized value or None."""
    if not _require(errors, row, column, value):
        return None
    normalized = _parse_date(value)
    if normalized is None:
        errors.append(
            _err(row, column, value, "Invalid date format — expected YYYY-MM-DD")
        )
        return None
    return normalized


def _require_numeric(errors: list, row: int, column: str, value: str):
    if _require(errors, row, column, value):
        try:
            float(value)
        except ValueError:
            errors.append(_err(row, column, value, "Must be a numeric value"))


def _read_csv(content: bytes) -> tuple[list[dict], list[str]]:
    """Return (rows, fieldnames)."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    fieldnames = list(reader.fieldnames or [])
    rows = list(reader)
    return rows, fieldnames


def _check_columns(required: set, fieldnames: list):
    missing = required - set(fieldnames)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {sorted(missing)}",
        )


def _raise_if_errors(errors: list):
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Validation failed with {len(errors)} error(s). No data was saved.",
                "errors": errors,
            },
        )


# ---------------------------------------------------------------------------
# CSV template definitions  (headers, [sample row])
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, tuple[list[str], list[str]]] = {
    "attendance": (
        ["event_title", "event_type", "event_description", "event_date", "data"],
        [
            "Sunday Mass",
            "mass",
            "Regular Sunday Mass",
            "2024-01-07",
            '{"attendees": 120}',
        ],
    ),
    "members": (
        [
            "first_name",
            "last_name",
            "email",
            "phone",
            "residence",
            "next_of_kin_first_name",
            "next_of_kin_last_name",
            "next_of_kin_email",
            "next_of_kin_phone",
            "next_of_kin_residence",
            "member_group",
        ],
        [
            "Jane",
            "Doe",
            "jane.doe@example.com",
            "+254700000000",
            "Nairobi",
            "John",
            "Doe",
            "john.doe@example.com",
            "+254711111111",
            "Nairobi",
            "youth",
        ],
    ),
    "parishes": (
        [
            "parish_name",
            "contact_email",
            "contact_phone",
            "member_number_prefix",
            "member_number_suffix",
        ],
        ["St. Mary Parish", "info@stmary.org", "+254700000000", "STM", "001"],
    ),
    "fund-projects": (
        ["name", "description", "target_amount", "current_amount"],
        ["Church Renovation", "Main hall renovation project", "500000", "0"],
    ),
    "roles": (
        ["title", "description"],
        ["Parish Secretary", "Handles administrative records"],
    ),
    "sacraments": (
        ["name", "rules", "fee_amount"],
        ["Baptism", "Must be below 3 months old", "500"],
    ),
    "sacrament-records": (
        ["sacrament_name", "data", "generate_certificate", "outstanding_balance"],
        ["Baptism", '{"name": "John Doe", "dob": "2024-01-01"}', "false", "0"],
    ),
    "certificates": (
        ["sacrament_record_name"],
        ["Jane Doe"],
    ),
    "collections": (
        [
            "collection_type",
            "collection_method",
            "amount",
            "member_number",
            "project_name",
            "sacrament_record_reference_no",
            "contributor_name",
            "contributor_phone",
            "description",
        ],
        [
            "offering",
            "cash",
            "500",
            "STM-001",
            "",
            "",
            "John Doe",
            "+254700000000",
            "Sunday offering",
        ],
    ),
    "users": (
        ["first_name", "last_name", "email", "phone", "role_name"],
        ["Alice", "Smith", "alice@example.com", "+254722000000", "Parish Secretary"],
    ),
}


@router.get("/template/{resource_type}")
async def download_template(
    resource_type: str,
    sacrament: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Download a CSV template for the given resource type.
    Supported: attendance, members, parishes, fund-projects, roles,
               sacraments, sacrament-records, certificates, collections, users

    For sacrament-records, pass ?sacrament=<name> to get a sacrament-specific
    template (without the sacrament_name column).
    """
    if resource_type == "sacrament-records" and sacrament:
        sacrament_name_clean = sacrament.strip()
        exists = (
            db.query(Sacrament)
            .filter(
                func.lower(Sacrament.name) == sacrament_name_clean.lower(),
                Sacrament.is_archived == False,
            )
            .first()
        )
        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Sacrament '{sacrament_name_clean}' does not exist.",
            )
        headers = ["data", "generate_certificate", "outstanding_balance"]
        sample = ['{"name": "John Doe", "dob": "2024-01-01"}', "false", "0"]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        writer.writerow(sample)
        buf.seek(0)
        filename = f"sacrament_records_{sacrament_name_clean.lower()}_template.csv"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    if resource_type not in _TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail=f"No template for '{resource_type}'. "
            f"Available: {sorted(_TEMPLATES.keys())}",
        )

    headers, sample = _TEMPLATES[resource_type]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerow(sample)
    buf.seek(0)

    filename = f"{resource_type}_template.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# bulk upload attendance records
# ---------------------------------------------------------------------------

@router.post("/attendance-records")
async def bulk_upload_attendance(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parish_id_for_bulk_upload: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
):
    parish_id = current_user.parish_id or parish_id_for_bulk_upload
    if not parish_id:
        raise HTTPException(
            status_code=400,
            detail="parish_id is required. System Admin must provide parish_id_for_bulk_upload as a query parameter.",
        )
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish_name = parish.parish_data.get("parish_name")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    rows, fieldnames = _read_csv(content)
    _check_columns({"event_title", "event_type", "event_description", "event_date", "data"}, fieldnames)

    errors: list = []
    for row_num, row in enumerate(rows, start=2):
        _require(errors, row_num, "event_title", row.get("event_title", "").strip())
        _require(errors, row_num, "event_type", row.get("event_type", "").strip())
        normalized_date = _require_date(errors, row_num, "event_date", row.get("event_date", "").strip())
        if normalized_date:
            row["event_date"] = normalized_date
        raw_data = row.get("data", "").strip()
        if _require(errors, row_num, "data", raw_data):
            try:
                json.loads(raw_data)
            except json.JSONDecodeError:
                errors.append(_err(row_num, "data", raw_data, "Must be valid JSON"))

    _raise_if_errors(errors)

    records: List[Attendance] = []
    for row in rows:
        records.append(
            Attendance(
                parish_id=parish_id,
                event_title=row["event_title"],
                event_type=row["event_type"],
                event_description=row["event_description"],
                event_date=row["event_date"],
                marked_by=current_user.id,
                data=json.loads(row["data"]),
            )
        )

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} attendance record(s) uploaded successfully to {parish_name}!",
    )
    logger.info(f"Successfully uploaded {len(records)} attendance records to {parish_name}!")
    return {"status": "success", "inserted": len(records)}


# ---------------------------------------------------------------------------
# bulk upload members
# ---------------------------------------------------------------------------

@router.post("/members")
async def bulk_upload_members(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parish_id_for_bulk_upload: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
):
    parish_id = current_user.parish_id or parish_id_for_bulk_upload
    if not parish_id:
        raise HTTPException(
            status_code=400,
            detail="parish_id is required. System Admin must provide parish_id_for_bulk_upload as a query parameter.",
        )
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish_name = parish.parish_data.get("parish_name")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    rows, fieldnames = _read_csv(content)
    _check_columns(
        {
            "first_name", "last_name", "email", "phone", "residence",
            "next_of_kin_first_name", "next_of_kin_last_name",
            "next_of_kin_email", "next_of_kin_phone", "next_of_kin_residence",
            "member_group",
        },
        fieldnames,
    )

    valid_groups = [g.value for g in MemberGroup]
    errors: list = []

    for row_num, row in enumerate(rows, start=2):
        _require(errors, row_num, "first_name", row.get("first_name", "").strip())
        _require(errors, row_num, "last_name", row.get("last_name", "").strip())
        _require_email(errors, row_num, "email", row.get("email", "").strip())
        _require(errors, row_num, "phone", row.get("phone", "").strip())

        group_val = row.get("member_group", "").strip().lower()
        if _require(errors, row_num, "member_group", group_val):
            if group_val not in valid_groups:
                errors.append(
                    _err(
                        row_num,
                        "member_group",
                        group_val,
                        f"Invalid value. Allowed: {valid_groups}",
                    )
                )

        # NOK email optional — validate format only if provided
        nok_email = row.get("next_of_kin_email", "").strip()
        if nok_email and not EMAIL_RE.match(nok_email):
            errors.append(_err(row_num, "next_of_kin_email", nok_email, "Invalid email format"))

    _raise_if_errors(errors)

    records: List[Member] = []
    for row in rows:
        next_of_kin = NextOfKinDetails(
            first_name=row.get("next_of_kin_first_name"),
            last_name=row.get("next_of_kin_last_name"),
            email=row.get("next_of_kin_email"),
            phone=row.get("next_of_kin_phone"),
            residence=row.get("next_of_kin_residence"),
        )
        member_data = MemberData(
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"],
            phone=row["phone"],
            residence=row["residence"],
            next_of_kin_details=next_of_kin,
        )
        payload = MemberCreate(
            parish_id=parish_id,
            member_data=member_data,
            member_group=MemberGroup(row["member_group"].lower().strip()),
        )
        record = Member(
            parish_id=payload.parish_id,
            member_no=generate_member_no(db, parish_id),
            member_group=payload.member_group.value,
            member_data=payload.member_data.dict(),
            is_archived=False,
        )
        records.append(record)

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} member(s) uploaded successfully to {parish_name}!",
    )
    logger.info(f"Successfully uploaded {len(records)} members to {parish_name}!")
    return {"status": "success", "inserted": len(records)}


# ---------------------------------------------------------------------------
# bulk upload parishes
# ---------------------------------------------------------------------------

@router.post("/parishes")
async def bulk_upload_parishes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    rows, fieldnames = _read_csv(content)
    _check_columns(
        {
            "parish_name", "contact_email", "contact_phone",
            "member_number_prefix", "member_number_suffix",
        },
        fieldnames,
    )

    errors: list = []
    for row_num, row in enumerate(rows, start=2):
        _require(errors, row_num, "parish_name", row.get("parish_name", "").strip())
        _require_email(errors, row_num, "contact_email", row.get("contact_email", "").strip())
        _require(errors, row_num, "contact_phone", row.get("contact_phone", "").strip())
        _require(errors, row_num, "member_number_prefix", row.get("member_number_prefix", "").strip())
        _require(errors, row_num, "member_number_suffix", row.get("member_number_suffix", "").strip())

    _raise_if_errors(errors)

    records: List[Parish] = []
    parish_names = []
    for row in rows:
        parish_data = {
            "parish_name": row["parish_name"],
            "contact_email": row["contact_email"],
            "contact_phone": row["contact_phone"],
            "parish_slug": generate_unique_slug(row["parish_name"], db),
        }
        records.append(
            Parish(
                parish_data=parish_data,
                member_number_prefix=row["member_number_prefix"],
                member_number_suffix=row["member_number_suffix"],
                parish_settings={},
                is_archived=False,
            )
        )
        parish_names.append(row["parish_name"])

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=current_user.parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} parish(es) uploaded successfully!",
    )
    logger.info(f"Successfully uploaded {len(records)} parishes!")
    return {"status": "success", "inserted": len(records)}


# ---------------------------------------------------------------------------
# bulk upload fund projects
# ---------------------------------------------------------------------------

@router.post("/fund-projects")
async def bulk_upload_fund_projects(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parish_id_for_bulk_upload: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
):
    parish_id = current_user.parish_id or parish_id_for_bulk_upload
    if not parish_id:
        raise HTTPException(
            status_code=400,
            detail="parish_id is required. System Admin must provide parish_id_for_bulk_upload as a query parameter.",
        )
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish_name = parish.parish_data.get("parish_name")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    rows, fieldnames = _read_csv(content)
    _check_columns({"name", "description", "target_amount", "current_amount"}, fieldnames)

    errors: list = []
    for row_num, row in enumerate(rows, start=2):
        _require(errors, row_num, "name", row.get("name", "").strip())
        _require_numeric(errors, row_num, "target_amount", row.get("target_amount", "").strip())
        _require_numeric(errors, row_num, "current_amount", row.get("current_amount", "").strip())

    _raise_if_errors(errors)

    records: List[FundProject] = []
    for row in rows:
        target = float(row["target_amount"])
        current = float(row["current_amount"])
        records.append(
            FundProject(
                parish_id=parish_id,
                name=row["name"],
                description=row["description"],
                account_suffix=generate_account_suffix(row["name"], parish_id, db),
                target_amount=target,
                current_amount=current,
                status="completed" if current >= target else "active",
                is_archived=False,
            )
        )

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} fund project(s) uploaded successfully to {parish_name}!",
    )
    logger.info(f"Successfully uploaded {len(records)} fund projects to {parish_name}!")
    return {"status": "success", "inserted": len(records)}


# ---------------------------------------------------------------------------
# bulk upload roles
# ---------------------------------------------------------------------------

@router.post("/roles")
async def bulk_upload_roles(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    rows, fieldnames = _read_csv(content)
    _check_columns({"title", "description"}, fieldnames)

    errors: list = []
    for row_num, row in enumerate(rows, start=2):
        _require(errors, row_num, "title", row.get("title", "").strip())

    _raise_if_errors(errors)

    records: List[Role] = []
    for row in rows:
        records.append(
            Role(
                title=row["title"],
                description=row["description"],
                is_archived=False,
            )
        )

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=current_user.parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} role(s) uploaded successfully!",
    )
    logger.info(f"Successfully uploaded {len(records)} roles")
    return {"status": "success", "inserted": len(records)}


# ---------------------------------------------------------------------------
# bulk upload sacraments
# ---------------------------------------------------------------------------

@router.post("/sacraments")
async def bulk_upload_sacraments(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parish_id_for_bulk_upload: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
):
    parish_id = current_user.parish_id or parish_id_for_bulk_upload
    if not parish_id:
        raise HTTPException(
            status_code=400,
            detail="parish_id is required. System Admin must provide parish_id_for_bulk_upload as a query parameter.",
        )
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish_name = parish.parish_data.get("parish_name")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    rows, fieldnames = _read_csv(content)
    _check_columns({"name", "rules", "fee_amount"}, fieldnames)

    errors: list = []
    for row_num, row in enumerate(rows, start=2):
        _require(errors, row_num, "name", row.get("name", "").strip())
        _require_numeric(errors, row_num, "fee_amount", row.get("fee_amount", "").strip())

    _raise_if_errors(errors)

    records: List[Sacrament] = []
    for row in rows:
        records.append(
            Sacrament(
                parish_id=parish_id,
                name=row["name"],
                rules=row["rules"],
                fee_amount=row["fee_amount"],
                is_archived=False,
            )
        )

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} sacrament(s) uploaded successfully to {parish_name}!",
    )
    logger.info(f"Successfully uploaded {len(records)} sacraments to {parish_name}!")
    return {"status": "success", "inserted": len(records)}


# ---------------------------------------------------------------------------
# bulk upload sacrament records
# ---------------------------------------------------------------------------

@router.post(
    "/sacrament-records",
    summary="Bulk upload sacrament records from a CSV file",
    description="""
Upload multiple sacrament records via CSV.

**CSV columns:**

| Column | Required | Notes |
|---|---|---|
| `sacrament_name` | Yes (omit when `?sacrament=` query param is used) | Name of the sacrament (must exist and be configured for the parish) |
| `data` | Yes | JSON object containing sacrament-specific fields (e.g. `{"name": "John Doe", "dob": "2024-01-01"}`) |
| `generate_certificate` | No | `true` or `false` (defaults to `false`) |
| `outstanding_balance` | No | Numeric value; defaults to the sacrament's `fee_amount` |

**Auto-generated / filled from context (do NOT include in CSV):**

- `id` — generated automatically (UUID)
- `reference_no` — generated automatically
- `parish_id` — taken from the authenticated user's token
- `sacrament_id` — resolved from `sacrament_name` column or `?sacrament=` query param
- `fee_amount` — taken from the sacrament's configured fee
- `created_by` — taken from the authenticated user's token
- `is_settled` — computed as `true` when `outstanding_balance <= 0`
- `is_archived` — defaults to `false`

**Query params:**
- `sacrament` (optional): Fix all rows to a single sacrament by name. When supplied the `sacrament_name` CSV column is not needed.
- `parish_id_for_bulk_upload` (optional): Required only for System Admins who are not scoped to a parish.
""",
)
async def bulk_upload_sacrament_records(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parish_id_for_bulk_upload: Optional[UUID] = Query(None),
    sacrament: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    parish_id = current_user.parish_id or parish_id_for_bulk_upload
    if not parish_id:
        raise HTTPException(
            status_code=400,
            detail="parish_id is required. System Admin must provide parish_id_for_bulk_upload as a query parameter.",
        )
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish_name = parish.parish_data.get("parish_name")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    # When a sacrament name is passed as a query param, the CSV has no
    # sacrament_name column — every row belongs to that one sacrament.
    fixed_sacrament: Sacrament | None = None
    if sacrament:
        sacrament_name_clean = sacrament.strip()
        globally = (
            db.query(Sacrament)
            .filter(
                func.lower(Sacrament.name) == sacrament_name_clean.lower(),
                Sacrament.is_archived == False,
            )
            .first()
        )
        if not globally:
            raise HTTPException(
                status_code=404,
                detail=f"Sacrament '{sacrament_name_clean}' does not exist.",
            )
        fixed_sacrament = (
            db.query(Sacrament)
            .filter(
                func.lower(Sacrament.name) == sacrament_name_clean.lower(),
                Sacrament.parish_id == parish_id,
                Sacrament.is_archived == False,
            )
            .first()
        )
        if not fixed_sacrament:
            raise HTTPException(
                status_code=404,
                detail=f"Sacrament '{sacrament_name_clean}' is not configured for this parish.",
            )

    content = await file.read()
    rows, fieldnames = _read_csv(content)

    if fixed_sacrament:
        required_cols = {"data"}
    else:
        required_cols = {"sacrament_name", "data"}
    _check_columns(required_cols, fieldnames)

    # For the multi-sacrament path, build a parish-scoped lookup
    sacrament_lookup: dict[str, Sacrament] = {}
    if not fixed_sacrament:
        parish_sacraments = (
            db.query(Sacrament)
            .filter(Sacrament.parish_id == parish_id, Sacrament.is_archived == False)
            .all()
        )
        sacrament_lookup = {s.name.lower().strip(): s for s in parish_sacraments}

    errors: list = []
    for row_num, row in enumerate(rows, start=2):
        if fixed_sacrament is None:
            sacrament_name_val = row.get("sacrament_name", "").strip().lower()
            if _require(errors, row_num, "sacrament_name", sacrament_name_val):
                if sacrament_name_val not in sacrament_lookup:
                    errors.append(
                        _err(
                            row_num,
                            "sacrament_name",
                            sacrament_name_val,
                            f"Sacrament not found for this parish. Available: {sorted(sacrament_lookup.keys())}",
                        )
                    )

        raw_data = row.get("data", "").strip()
        if _require(errors, row_num, "data", raw_data):
            try:
                parsed = json.loads(raw_data)
                if not isinstance(parsed, dict):
                    errors.append(
                        _err(row_num, "data", raw_data, "Must be a JSON object (dict), not a list or scalar")
                    )
            except json.JSONDecodeError:
                errors.append(_err(row_num, "data", raw_data, "Must be valid JSON (e.g. {\"name\": \"John Doe\"})"))

        outstanding_bal = row.get("outstanding_balance", "").strip() or "0"
        try:
            float(outstanding_bal)
        except ValueError:
            errors.append(
                _err(row_num, "outstanding_balance", outstanding_bal, "Must be a numeric value")
            )

        gen_cert = row.get("generate_certificate", "").strip().lower()
        if gen_cert and gen_cert not in ("true", "false", "1", "0", "yes", "no"):
            errors.append(
                _err(row_num, "generate_certificate", gen_cert, "Must be true or false")
            )

    _raise_if_errors(errors)

    records: List[SacramentRecord] = []
    for row in rows:
        if fixed_sacrament:
            sacrament_obj = fixed_sacrament
            sacrament_name_key = fixed_sacrament.name.lower().strip()
        else:
            sacrament_name_key = row["sacrament_name"].lower().strip()
            sacrament_obj = sacrament_lookup[sacrament_name_key]

        data = json.loads(row["data"].strip())
        outstanding_balance = float(row.get("outstanding_balance", "") or sacrament_obj.fee_amount or 0)
        gen_cert_raw = row.get("generate_certificate", "").strip().lower()
        generate_certificate = gen_cert_raw in ("true", "1", "yes")

        records.append(
            SacramentRecord(
                reference_no=generate_sacrament_record_reference_number(sacrament_name_key, db),
                parish_id=parish_id,
                sacrament_id=sacrament_obj.id,
                data=data,
                generate_certificate=generate_certificate,
                fee_amount=sacrament_obj.fee_amount,
                outstanding_balance=outstanding_balance,
                is_settled=(outstanding_balance <= 0),
                created_by=current_user.id,
                is_archived=False,
            )
        )

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} sacrament record(s) uploaded successfully to {parish_name}!",
    )
    logger.info(f"Successfully uploaded {len(records)} sacrament records to {parish_name}!")
    return {"status": "success", "inserted": len(records)}


# ---------------------------------------------------------------------------
# bulk upload certificates
# ---------------------------------------------------------------------------

@router.post("/certificates")
async def bulk_upload_certificates(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parish_id_for_bulk_upload: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
):
    parish_id = current_user.parish_id or parish_id_for_bulk_upload
    if not parish_id:
        raise HTTPException(
            status_code=400,
            detail="parish_id is required. System Admin must provide parish_id_for_bulk_upload as a query parameter.",
        )
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish_name = parish.parish_data.get("parish_name")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    rows, fieldnames = _read_csv(content)
    _check_columns({"sacrament_record_name"}, fieldnames)

    errors: list = []
    for row_num, row in enumerate(rows, start=2):
        name_val = row.get("sacrament_record_name", "").strip()
        if _require(errors, row_num, "sacrament_record_name", name_val):
            match = (
                db.query(SacramentRecord)
                .filter(
                    cast(SacramentRecord.data["name"], String).ilike(f"%{name_val.lower()}%")
                )
                .first()
            )
            if not match:
                errors.append(
                    _err(
                        row_num,
                        "sacrament_record_name",
                        name_val,
                        "No matching sacrament record found for this name",
                    )
                )

    _raise_if_errors(errors)

    records: List[Certificate] = []
    for row in rows:
        name_val = row["sacrament_record_name"].strip().lower()
        sacrament_record = (
            db.query(SacramentRecord)
            .filter(cast(SacramentRecord.data["name"], String).ilike(f"%{name_val}%"))
            .first()
        )
        records.append(
            Certificate(
                parish_id=parish_id,
                sacrament_record_id=sacrament_record.id,
                certificate_for=sacrament_record.data["name"],
                certificate_no=generate_unique_certificate_number(db),
                generated_by=current_user.id,
                is_archived=False,
            )
        )

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} certificate(s) uploaded successfully to {parish_name}!",
    )
    logger.info(f"Successfully uploaded {len(records)} certificates to {parish_name}!")
    return {"status": "success", "inserted": len(records)}


# ---------------------------------------------------------------------------
# bulk upload users
# ---------------------------------------------------------------------------

@router.post("/users")
async def bulk_upload_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parish_id_for_bulk_upload: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
):
    parish_id = current_user.parish_id or parish_id_for_bulk_upload
    if not parish_id:
        raise HTTPException(
            status_code=400,
            detail="parish_id is required. System Admin must provide parish_id_for_bulk_upload as a query parameter.",
        )
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish_name = parish.parish_data.get("parish_name")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    rows, fieldnames = _read_csv(content)
    _check_columns({"first_name", "last_name", "email", "phone", "role_name"}, fieldnames)

    errors: list = []
    for row_num, row in enumerate(rows, start=2):
        _require(errors, row_num, "first_name", row.get("first_name", "").strip())
        _require(errors, row_num, "last_name", row.get("last_name", "").strip())
        _require_email(errors, row_num, "email", row.get("email", "").strip())
        _require(errors, row_num, "phone", row.get("phone", "").strip())
        role_name = row.get("role_name", "").strip().lower()
        if _require(errors, row_num, "role_name", role_name):
            role = db.query(Role).filter(func.lower(Role.title) == role_name).first()
            if not role:
                errors.append(
                    _err(row_num, "role_name", role_name, "No role found with this name")
                )

    _raise_if_errors(errors)

    records: List[User] = []
    for row in rows:
        role = db.query(Role).filter(func.lower(Role.title) == row["role_name"].strip().lower()).first()
        records.append(
            User(
                parish_id=parish_id,
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row["email"],
                phone=row["phone"],
                hashed_password=hash_password("password"),
                role_id=role.id,
                is_active=True,
                is_archived=False,
            )
        )

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} user(s) uploaded successfully to {parish_name}!",
    )
    logger.info(f"Successfully uploaded {len(records)} users to {parish_name}!")
    return {"status": "success", "inserted": len(records)}


# ---------------------------------------------------------------------------
# bulk upload collections
# ---------------------------------------------------------------------------

_VALID_COLLECTION_TYPES = {ct.value for ct in CollectionType}
_VALID_COLLECTION_METHODS = {cm.value for cm in CollectionMethod}


@router.post("/collections")
async def bulk_upload_collections(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parish_id_for_bulk_upload: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
):
    parish_id = current_user.parish_id or parish_id_for_bulk_upload
    if not parish_id:
        raise HTTPException(
            status_code=400,
            detail="parish_id is required. System Admin must provide parish_id_for_bulk_upload as a query parameter.",
        )
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found!")
    parish_name = parish.parish_data.get("parish_name")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    rows, fieldnames = _read_csv(content)
    _check_columns({"collection_type", "collection_method", "amount"}, fieldnames)

    # Pre-build lookups for names → IDs (case-insensitive)
    fund_project_lookup = {
        fp.name.strip().lower(): fp
        for fp in db.query(FundProject).filter(FundProject.parish_id == parish_id).all()
        if fp.name
    }
    member_lookup = {
        m.member_no.strip().lower(): m
        for m in db.query(Member).filter(Member.parish_id == parish_id, Member.is_archived == False).all()
        if m.member_no
    }

    errors: list = []
    for row_num, row in enumerate(rows, start=2):
        # collection_type — required, must be a valid enum value
        col_type = row.get("collection_type", "").strip().lower()
        if _require(errors, row_num, "collection_type", col_type):
            if col_type not in _VALID_COLLECTION_TYPES:
                errors.append(
                    _err(
                        row_num,
                        "collection_type",
                        col_type,
                        f"Invalid type. Must be one of: {sorted(_VALID_COLLECTION_TYPES)}",
                    )
                )

        # collection_method — required, must be a valid enum value
        col_method = row.get("collection_method", "").strip().lower()
        if _require(errors, row_num, "collection_method", col_method):
            if col_method not in _VALID_COLLECTION_METHODS:
                errors.append(
                    _err(
                        row_num,
                        "collection_method",
                        col_method,
                        f"Invalid method. Must be one of: {sorted(_VALID_COLLECTION_METHODS)}",
                    )
                )

        # amount — required numeric
        _require_numeric(errors, row_num, "amount", row.get("amount", "").strip())

        # member_number — optional, but must exist if provided
        member_no = row.get("member_number", "").strip().lower()
        if member_no and member_no not in member_lookup:
            errors.append(
                _err(
                    row_num,
                    "member_number",
                    member_no,
                    "No member found with this member number in this parish",
                )
            )

        # project_name — required when collection_type=project
        project_name = row.get("project_name", "").strip().lower()
        if col_type == "project":
            if not project_name:
                errors.append(
                    _err(
                        row_num,
                        "project_name",
                        "",
                        "'project_name' is required when collection_type is 'project'",
                    )
                )
            elif project_name not in fund_project_lookup:
                errors.append(
                    _err(
                        row_num,
                        "project_name",
                        project_name,
                        f"No fund project found with this name. Available: {sorted(fund_project_lookup.keys())}",
                    )
                )

        # sacrament_record_reference_no — required when collection_type=sacrament
        sacrament_record_ref = row.get("sacrament_record_reference_no", "").strip()
        if col_type == "sacrament":
            if not sacrament_record_ref:
                errors.append(
                    _err(
                        row_num,
                        "sacrament_record_reference_no",
                        "",
                        "'sacrament_record_reference_no' is required when collection_type is 'sacrament'",
                    )
                )
            else:
                match = (
                    db.query(SacramentRecord)
                    .filter(
                        SacramentRecord.parish_id == parish_id,
                        SacramentRecord.reference_no == sacrament_record_ref,
                    )
                    .first()
                )
                if not match:
                    errors.append(
                        _err(
                            row_num,
                            "sacrament_record_reference_no",
                            sacrament_record_ref,
                            "No sacrament record found with this reference number in this parish",
                        )
                    )

    _raise_if_errors(errors)

    records: List[Collection] = []
    for row in rows:
        col_type = row.get("collection_type", "").strip().lower()
        col_method = row.get("collection_method", "").strip().lower()
        amount = float(row.get("amount", "0").strip())

        # Resolve optional member
        member_no = row.get("member_number", "").strip().lower()
        member_obj = member_lookup.get(member_no) if member_no else None

        # Resolve optional project
        project_name = row.get("project_name", "").strip().lower()
        project_obj = fund_project_lookup.get(project_name) if project_name else None

        # Resolve optional sacrament record
        sacrament_record_ref = row.get("sacrament_record_reference_no", "").strip()
        sacrament_record_obj = None
        if sacrament_record_ref:
            sacrament_record_obj = (
                db.query(SacramentRecord)
                .filter(
                    SacramentRecord.parish_id == parish_id,
                    SacramentRecord.reference_no == sacrament_record_ref,
                )
                .first()
            )

        contributor_name = row.get("contributor_name", "").strip()
        contributor_phone = row.get("contributor_phone", "").strip()
        description = row.get("description", "").strip()

        collection_data = {}
        if description:
            collection_data["description"] = description

        contributor_data = {}
        if contributor_name:
            contributor_data["name"] = contributor_name
        if contributor_phone:
            contributor_data["phone"] = contributor_phone

        records.append(
            Collection(
                parish_id=parish_id,
                collection_type=CollectionType(col_type),
                collection_method=CollectionMethod(col_method),
                amount=amount,
                member_id=member_obj.id if member_obj else None,
                project_id=project_obj.id if project_obj else None,
                sacrament_record_id=sacrament_record_obj.id if sacrament_record_obj else None,
                collection_data=collection_data,
                contributor_data=contributor_data if contributor_data else None,
                recorded_by=current_user.id,
                is_archived=False,
            )
        )

    db.bulk_save_objects(records)
    db.commit()
    create_notification(
        db=db,
        user_id=current_user.id,
        parish_id=parish_id,
        notification_type=NotificationType.info,
        message=f"Bulk upload: {len(records)} collection(s) uploaded successfully to {parish_name}!",
    )
    logger.info(f"Successfully uploaded {len(records)} collections to {parish_name}!")
    return {"status": "success", "inserted": len(records)}
