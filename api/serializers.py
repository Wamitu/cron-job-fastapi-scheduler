# serializers (all together) to avoid circular imports


# serialize parish
def serialize_parish(parish):
    if isinstance(parish, dict):
        return parish

    return {
        "id": parish.id,
        "diocese_id": parish.diocese_id,
        "parish_data": parish.parish_data,
        "member_number_prefix": parish.member_number_prefix,
        "member_number_suffix": parish.member_number_suffix,
        "parish_settings": parish.parish_settings,
        "is_archived": parish.is_archived,
        "created_at": parish.created_at.isoformat() if parish.created_at else None,
        "updated_at": parish.updated_at.isoformat() if parish.updated_at else None,
    }


# serialize parishes
def serialize_parishes(parishes):
    return [serialize_parish(parish) for parish in parishes]


# serialize diocese
def serialize_diocese(diocese):
    if isinstance(diocese, dict):
        return diocese

    return {
        "id": diocese.id,
        "parishes": (
            [serialize_parish(parish) for parish in diocese.parishes]
            if diocese.parishes
            else []
        ),
        "name": diocese.name,
        "description": diocese.description,
        "created_at": diocese.created_at.isoformat() if diocese.created_at else None,
        "updated_at": diocese.updated_at.isoformat() if diocese.updated_at else None,
    }


# serialize dioceses
def serialize_dioceses(dioceses):
    return [serialize_diocese(diocese) for diocese in dioceses]


# serialize role
def serialize_role(role):
    if isinstance(role, dict):
        return role

    return {
        "id": role.id,
        "title": role.title,
        "description": role.description,
        "is_archived": role.is_archived,
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


# serialize roles
def serialize_roles(roles):
    return [serialize_role(role) for role in roles]


# serialize user
def serialize_user(user):
    if isinstance(user, dict):
        return user

    return {
        "id": user.id,
        "diocese_id": user.diocese_id if user.diocese_id else None,
        "diocese": serialize_diocese(user.diocese) if user.diocese else None,
        "parish_id": user.parish_id if user.parish_id else None,
        "parish": serialize_parish(user.parish) if user.parish else None,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "role_id": user.role_id,
        "role": serialize_role(user.role) if user.role else None,
        "is_active": user.is_active,
        "is_archived": user.is_archived,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


# serialize users
def serialize_users(users):
    return [serialize_user(user) for user in users]


# serialize attendance record
def serialize_attendance_record(attendance_record):
    if isinstance(attendance_record, dict):
        return attendance_record
    return {
        "id": attendance_record.id,
        "parish_id": attendance_record.parish_id,
        "parish": (
            serialize_parish(attendance_record.parish)
            if attendance_record.parish
            else None
        ),
        "event_title": attendance_record.event_title,
        "event_type": attendance_record.event_type,
        "event_description": attendance_record.event_description,
        "event_date": attendance_record.event_date,
        "marked_by": attendance_record.marked_by,
        "marked_by_user": (
            serialize_user(attendance_record.marked_by_user)
            if attendance_record.marked_by_user
            else None
        ),
        "data": attendance_record.data,
        "is_archived": attendance_record.is_archived,
        "created_at": (
            attendance_record.created_at.isoformat()
            if attendance_record.created_at
            else None
        ),
        "updated_at": (
            attendance_record.updated_at.isoformat()
            if attendance_record.updated_at
            else None
        ),
    }


# serialize attendance records
def serialize_attendance_records(attendance_records):
    return [
        serialize_attendance_record(attendance_record)
        for attendance_record in attendance_records
    ]


# serialize collection
def serialize_collection(collection):
    if isinstance(collection, dict):
        return collection
    return {
        "id": collection.id,
        "collection_type": collection.collection_type,
        "member_id": collection.member_id,
        "member": (serialize_member(collection.member) if collection.member else None),
        "parish_id": collection.parish_id,
        "parish": (serialize_parish(collection.parish) if collection.parish else None),
        "project_id": collection.project_id,
        "project": (
            serialize_fund_project(collection.project) if collection.project else None
        ),
        "sacrament_record_id": collection.sacrament_record_id,
        "record": (
            serialize_sacrament_record(collection.record) if collection.record else None
        ),
        "collection_method": collection.collection_method,
        "collection_data": collection.collection_data,
        "contributor_data": collection.contributor_data,
        "recorded_by": collection.recorded_by,
        "recorded_by_user": (
            serialize_user(collection.recorded_by_user)
            if collection.recorded_by_user
            else None
        ),
        "amount": collection.amount,
        "is_archived": collection.is_archived,
        "created_at": (
            collection.created_at.isoformat() if collection.created_at else None
        ),
    }


# serialize collections
def serialize_collections(collections):
    return [serialize_collection(collection) for collection in collections]


# serialize fund_project
def serialize_fund_project(fund_project):
    if isinstance(fund_project, dict):
        return fund_project
    return {
        "id": fund_project.id,
        "parish_id": fund_project.parish_id,
        "parish": (
            serialize_parish(fund_project.parish) if fund_project.parish else None
        ),
        "name": fund_project.name,
        "description": fund_project.description,
        "account_suffix": fund_project.account_suffix,
        "status": fund_project.status,
        "target_amount": fund_project.target_amount,
        "current_amount": fund_project.current_amount,
        "is_archived": fund_project.is_archived,
        "created_at": (
            fund_project.created_at.isoformat() if fund_project.created_at else None
        ),
    }


# serialize fund_projects
def serialize_fund_projects(fund_projects):
    return [serialize_fund_project(fund_project) for fund_project in fund_projects]


# serialize member
def serialize_member(member):
    if isinstance(member, dict):
        return member
    return {
        "id": member.id,
        "parish_id": member.parish_id,
        "parish": serialize_parish(member.parish) if member.parish else None,
        "member_no": member.member_no,
        "member_data": member.member_data,
        "member_group": member.member_group,
        "is_archived": member.is_archived,
        "created_at": (member.created_at.isoformat() if member.created_at else None),
        "updated_at": (member.updated_at.isoformat() if member.updated_at else None),
    }


# serialize members
def serialize_members(members):
    return [serialize_member(member) for member in members]


# serialize parish subscription
def serialize_parish_subscription(parish_subscription):
    if isinstance(parish_subscription, dict):
        return parish_subscription
    return {
        "id": parish_subscription.id,
        "parish_id": parish_subscription.parish_id,
        "parish": (
            serialize_parish(parish_subscription.parish)
            if parish_subscription.parish
            else None
        ),
        "subscription_plan_id": parish_subscription.subscription_plan_id,
        "subscription": (
            serialize_subscription_plan(parish_subscription.subscription)
            if parish_subscription.subscription
            else None
        ),
        "start_date": parish_subscription.start_date,
        "end_date": parish_subscription.end_date,
        "last_renewed_at": parish_subscription.last_renewed_at,
        "status": parish_subscription.status,
        "next_subscription_plan_id": parish_subscription.next_subscription_plan_id,
        "next_plan": (
            serialize_subscription_plan(parish_subscription.next_plan)
            if parish_subscription.next_plan
            else None
        ),
        "last_plan_change_at": parish_subscription.last_plan_change_at,
        "is_archived": parish_subscription.is_archived,
        "created_at": (
            parish_subscription.created_at.isoformat()
            if parish_subscription.created_at
            else None
        ),
        "updated_at": (
            parish_subscription.updated_at.isoformat()
            if parish_subscription.updated_at
            else None
        ),
    }


# serialize parish subscriptions
def serialize_parish_subscriptions(parish_subscriptions):
    return [
        serialize_parish_subscription(parish_subscription)
        for parish_subscription in parish_subscriptions
    ]


# serialize parish parish subscription
def serialize_parish_parish_subscription(parish_parish_subscription):
    plan = parish_parish_subscription.subscription
    features = [
        {
            "id": str(pivot.feature.id),
            "name": pivot.feature.name,
            "description": pivot.feature.description,
            "enabled": pivot.enabled,
            "is_inherited": pivot.is_inherited,
        }
        for pivot in plan.features_pivot
    ]

    return {
        "id": str(parish_parish_subscription.id),
        "parish_id": str(parish_parish_subscription.parish_id),
        "subscription": {
            "id": str(plan.id),
            "name": plan.name,
            "price": float(plan.price),
            "features": features,
        },
        "start_date": parish_parish_subscription.start_date.isoformat(),
        "end_date": (
            parish_parish_subscription.end_date.isoformat()
            if parish_parish_subscription.end_date
            else None
        ),
        "status": (
            parish_parish_subscription.status.name
            if parish_parish_subscription.status
            else None
        ),
        "created_at": (
            parish_parish_subscription.created_at.isoformat()
            if parish_parish_subscription.created_at
            else None
        ),
        "updated_at": (
            parish_parish_subscription.updated_at.isoformat()
            if parish_parish_subscription.updated_at
            else None
        ),
    }


# serialize sacrament record
def serialize_sacrament_record(sacrament_record):
    if isinstance(sacrament_record, dict):
        return sacrament_record
    return {
        "id": sacrament_record.id,
        "reference_no": sacrament_record.reference_no,
        "parish_id": sacrament_record.parish_id,
        "parish": (
            serialize_parish(sacrament_record.parish)
            if sacrament_record.parish
            else None
        ),
        "sacrament_id": sacrament_record.sacrament_id,
        "sacrament": (
            serialize_sacrament(sacrament_record.sacrament)
            if sacrament_record.sacrament
            else None
        ),
        "data": sacrament_record.data if isinstance(sacrament_record.data, dict) else {},
        "generate_certificate": sacrament_record.generate_certificate,
        "fee_amount": sacrament_record.fee_amount,
        "outstanding_balance": sacrament_record.outstanding_balance,
        "is_settled": sacrament_record.is_settled,
        "created_by": sacrament_record.created_by,
        "created_by_user": (
            serialize_user(sacrament_record.created_by_user)
            if sacrament_record.created_by_user
            else None
        ),
        "is_archived": sacrament_record.is_archived,
        "created_at": (
            sacrament_record.created_at.isoformat()
            if sacrament_record.created_at
            else None
        ),
        "updated_at": (
            sacrament_record.updated_at.isoformat()
            if sacrament_record.updated_at
            else None
        ),
    }


# serialize sacrament_records
def serialize_sacrament_records(sacrament_records):
    return [
        serialize_sacrament_record(sacrament_record)
        for sacrament_record in sacrament_records
    ]


# serialize sacrament
def serialize_sacrament(sacrament):
    if isinstance(sacrament, dict):
        return sacrament
    return {
        "id": sacrament.id,
        "parish_id": sacrament.parish_id,
        "parish": (serialize_parish(sacrament.parish) if sacrament.parish else None),
        "name": sacrament.name,
        "rules": sacrament.rules,
        "fee_amount": sacrament.fee_amount,
        "is_archived": sacrament.is_archived,
        "created_at": (
            sacrament.created_at.isoformat() if sacrament.created_at else None
        ),
        "updated_at": (
            sacrament.updated_at.isoformat() if sacrament.updated_at else None
        ),
    }


# serialize sacraments
def serialize_sacraments(sacraments):
    return [serialize_sacrament(sacrament) for sacrament in sacraments]


# serialize certificate
def serialize_certificate(certificate):
    if isinstance(certificate, dict):
        return certificate
    return {
        "id": certificate.id,
        "parish_id": certificate.parish_id,
        "parish": serialize_parish(certificate.parish) if certificate.parish else None,
        "sacrament_record_id": certificate.sacrament_record_id,
        "sacrament_record": (
            serialize_sacrament_record(certificate.sacrament_record)
            if certificate.sacrament_record
            else None
        ),
        "certificate_for": certificate.certificate_for,
        "certificate_no": certificate.certificate_no,
        "generated_by": certificate.generated_by,
        "generated_by_user": (
            serialize_user(certificate.generated_by_user)
            if certificate.generated_by_user
            else None
        ),
        "is_archived": certificate.is_archived,
        "created_at": (
            certificate.created_at.isoformat() if certificate.created_at else None
        ),
        "updated_at": (
            certificate.updated_at.isoformat() if certificate.updated_at else None
        ),
    }


# serialize certificates
def serialize_certificates(certificates):
    return [serialize_certificate(certificate) for certificate in certificates]


# serialize subscription payment
def serialize_subscription_payment(subscription_payment):
    if isinstance(subscription_payment, dict):
        return subscription_payment
    return {
        "id": subscription_payment.id,
        "parish_subscription_id": subscription_payment.parish_subscription_id,
        "parish_subscription": (
            serialize_parish_subscription(subscription_payment.parish_subscription)
            if subscription_payment.parish_subscription
            else None
        ),
        "amount": subscription_payment.amount,
        "channel": subscription_payment.channel,
        "reference": subscription_payment.reference,
        "paid_at": subscription_payment.paid_at,
        "recorded_by": subscription_payment.recorded_by,
        "recorded_by_user": (
            serialize_user(subscription_payment.recorded_by_user)
            if subscription_payment.recorded_by_user
            else None
        ),
        "is_archived": subscription_payment.is_archived,
        "created_at": (
            subscription_payment.created_at.isoformat()
            if subscription_payment.created_at
            else None
        ),
    }


# serialize subscription payments
def serialize_subscription_payments(subscription_payments):
    return [
        serialize_subscription_payment(subscription_payment)
        for subscription_payment in subscription_payments
    ]


# serialize subscription plan feature
def serialize_subscription_plan_feature(subscription_plan_feature):
    if isinstance(subscription_plan_feature, dict):
        return subscription_plan_feature
    return {
        "id": subscription_plan_feature.id,
        "name": subscription_plan_feature.name,
        "description": subscription_plan_feature.description,
        "created_at": (
            subscription_plan_feature.created_at.isoformat()
            if subscription_plan_feature.created_at
            else None
        ),
        "updated_at": (
            subscription_plan_feature.updated_at.isoformat()
            if subscription_plan_feature.updated_at
            else None
        ),
    }


# serialize subscription plans
def serialize_subscription_plan_features(subscription_plan_features):
    return [
        serialize_subscription_plan_feature(subscription_plan_feature)
        for subscription_plan_feature in subscription_plan_features
    ]


# serialize subscription plan
def serialize_subscription_plan(subscription_plan):
    if isinstance(subscription_plan, dict):
        return subscription_plan
    return {
        "id": subscription_plan.id,
        "name": subscription_plan.name,
        "price": subscription_plan.price,
        "features": (
            [
                {
                    "id": pivot.feature.id,
                    "name": pivot.feature.name,
                    "description": pivot.feature.description,
                    "enabled": pivot.enabled,
                }
                for pivot in subscription_plan.features_pivot
                if pivot.enabled
            ]
            if hasattr(subscription_plan, "features_pivot")
            and subscription_plan.features_pivot
            else []
        ),
        "created_at": (
            subscription_plan.created_at.isoformat()
            if subscription_plan.created_at
            else None
        ),
        "updated_at": (
            subscription_plan.updated_at.isoformat()
            if subscription_plan.updated_at
            else None
        ),
    }


# serialize subscription plans
def serialize_subscription_plans(subscription_plans):
    return [
        serialize_subscription_plan(subscription_plan)
        for subscription_plan in subscription_plans
    ]


# ─── Export serializers (flat, human-readable, for CSV downloads) ─────────────

def _export_parish_name(parish):
    """Extract a plain parish name string from a Parish ORM object."""
    if not parish:
        return None
    return (parish.parish_data or {}).get("parish_name")


def export_attendance_record(r):
    return {
        "Event Title": r.event_title,
        "Event Type": r.event_type,
        "Event Description": r.event_description,
        "Event Date": r.event_date.isoformat() if r.event_date else None,
        "Parish": _export_parish_name(r.parish),
        "Marked By": (
            f"{r.marked_by_user.first_name} {r.marked_by_user.last_name}".strip()
            if r.marked_by_user else None
        ),
        "Date Recorded": r.created_at.isoformat() if r.created_at else None,
    }


def export_attendance_records(records):
    return [export_attendance_record(r) for r in records]


def export_certificate(c):
    sacrament_name = None
    if c.sacrament_record and c.sacrament_record.sacrament:
        sacrament_name = c.sacrament_record.sacrament.name
    return {
        "Certificate No": c.certificate_no,
        "Certificate For": c.certificate_for,
        "Sacrament": sacrament_name,
        "Parish": _export_parish_name(c.parish),
        "Generated By": (
            f"{c.generated_by_user.first_name} {c.generated_by_user.last_name}".strip()
            if c.generated_by_user else None
        ),
        "Date Generated": c.created_at.isoformat() if c.created_at else None,
    }


def export_certificates(certificates):
    return [export_certificate(c) for c in certificates]


def export_collection(c):
    member_name = None
    if c.member:
        md = c.member.member_data or {}
        member_name = f"{md.get('first_name', '')} {md.get('last_name', '')}".strip() or None
    return {
        "Collection Type": c.collection_type,
        "Collection Method": c.collection_method,
        "Amount": c.amount,
        "Member": member_name,
        "Project": c.project.name if c.project else None,
        "Parish": _export_parish_name(c.parish),
        "Recorded By": (
            f"{c.recorded_by_user.first_name} {c.recorded_by_user.last_name}".strip()
            if c.recorded_by_user else None
        ),
        "Date Recorded": c.created_at.isoformat() if c.created_at else None,
    }


def export_collections(collections):
    return [export_collection(c) for c in collections]


def export_fund_project(fp):
    return {
        "Name": fp.name,
        "Description": fp.description,
        "Status": fp.status,
        "Target Amount": fp.target_amount,
        "Current Amount": fp.current_amount,
        "Account Suffix": fp.account_suffix,
        "Parish": _export_parish_name(fp.parish),
        "Created At": fp.created_at.isoformat() if fp.created_at else None,
    }


def export_fund_projects(fund_projects):
    return [export_fund_project(fp) for fp in fund_projects]


def export_member(m):
    md = m.member_data or {}
    nok = md.get("next_of_kin_details") or {}
    if isinstance(nok, str):
        import json as _json
        try:
            nok = _json.loads(nok)
        except Exception:
            nok = {}
    return {
        "Member No": m.member_no,
        "First Name": md.get("first_name"),
        "Last Name": md.get("last_name"),
        "Email": md.get("email"),
        "Phone": md.get("phone"),
        "Residence": md.get("residence"),
        "Next of Kin Name": nok.get("name"),
        "Next of Kin Phone": nok.get("phone"),
        "Member Group": m.member_group,
        "Parish": _export_parish_name(m.parish),
        "Date Registered": m.created_at.isoformat() if m.created_at else None,
    }


def export_members(members):
    return [export_member(m) for m in members]


def export_parish(p):
    pd = p.parish_data or {}
    diocese_name = p.diocese.name if hasattr(p, "diocese") and p.diocese else None
    return {
        "Parish Name": pd.get("parish_name"),
        "Email": pd.get("email"),
        "Phone": pd.get("phone"),
        "Address": pd.get("address"),
        "Diocese": diocese_name,
        "Member Number Prefix": p.member_number_prefix,
        "Created At": p.created_at.isoformat() if p.created_at else None,
    }


def export_parishes(parishes):
    return [export_parish(p) for p in parishes]


def export_role(r):
    return {
        "Title": r.title,
        "Description": r.description,
        "Created At": r.created_at.isoformat() if r.created_at else None,
    }


def export_roles(roles):
    return [export_role(r) for r in roles]


def export_sacrament(s):
    return {
        "Name": s.name,
        "Parish": _export_parish_name(s.parish),
        "Fee Amount": s.fee_amount,
        "Created At": s.created_at.isoformat() if s.created_at else None,
    }


def export_sacraments(sacraments):
    return [export_sacrament(s) for s in sacraments]


def export_sacrament_record(r):
    sacrament_name = r.sacrament.name if r.sacrament else None
    created_by_name = (
        f"{r.created_by_user.first_name} {r.created_by_user.last_name}".strip()
        if r.created_by_user else None
    )
    data = r.data or {}
    name = (
        data.get("name")
        or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        or None
    )
    return {
        "Reference No": r.reference_no,
        "Sacrament": sacrament_name,
        "Name": name,
        "Parish": _export_parish_name(r.parish),
        "Fee Amount": r.fee_amount,
        "Outstanding Balance": r.outstanding_balance,
        "Is Settled": "Yes" if r.is_settled else "No",
        "Created By": created_by_name,
        "Date Created": r.created_at.isoformat() if r.created_at else None,
    }


def export_sacrament_records(sacrament_records):
    return [export_sacrament_record(r) for r in sacrament_records]


def export_parish_subscription(ps):
    status = ps.status.value if hasattr(ps.status, "value") else ps.status
    return {
        "Parish": _export_parish_name(ps.parish),
        "Subscription Plan": ps.subscription.name if ps.subscription else None,
        "Status": status,
        "Start Date": ps.start_date.isoformat() if ps.start_date else None,
        "End Date": ps.end_date.isoformat() if ps.end_date else None,
        "Last Renewed": ps.last_renewed_at.isoformat() if ps.last_renewed_at else None,
        "Created At": ps.created_at.isoformat() if ps.created_at else None,
    }


def export_parish_subscriptions(subscriptions):
    return [export_parish_subscription(ps) for ps in subscriptions]


def export_subscription_payment(payment):
    parish_name = None
    if payment.parish_subscription and payment.parish_subscription.parish:
        parish_name = (payment.parish_subscription.parish.parish_data or {}).get("parish_name")
    return {
        "Amount": payment.amount,
        "Channel": payment.channel,
        "Reference": payment.reference,
        "Parish": parish_name,
        "Paid At": payment.paid_at.isoformat() if payment.paid_at else None,
        "Date Recorded": payment.created_at.isoformat() if payment.created_at else None,
    }


def export_subscription_payments(payments):
    return [export_subscription_payment(p) for p in payments]


def export_invited_user(u):
    invited_by_name = (
        f"{u.invited_by_user.first_name} {u.invited_by_user.last_name}".strip()
        if u.invited_by_user else None
    )
    return {
        "First Name": u.first_name,
        "Last Name": u.last_name,
        "Email": u.email,
        "Phone": u.phone,
        "Role": u.role.title if u.role else None,
        "Parish": _export_parish_name(u.parish),
        "Invited By": invited_by_name,
        "Date Invited": u.created_at.isoformat() if u.created_at else None,
    }


def export_invited_users(invited_users):
    return [export_invited_user(u) for u in invited_users]


def export_user(u):
    parish_name = _export_parish_name(u.parish) if hasattr(u, "parish") and u.parish else None
    diocese_name = u.diocese.name if hasattr(u, "diocese") and u.diocese else None
    return {
        "First Name": u.first_name,
        "Last Name": u.last_name,
        "Email": u.email,
        "Phone": u.phone,
        "Role": u.role.title if u.role else None,
        "Parish": parish_name,
        "Diocese": diocese_name,
        "Is Active": "Yes" if u.is_active else "No",
        "Date Created": u.created_at.isoformat() if u.created_at else None,
    }


def export_users(users):
    return [export_user(u) for u in users]
