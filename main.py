from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer
from api import (
    attendance_router,
    audit_log_router,
    bulk_upload_router,
    collections_router,
    dashboard_analytics_router,
    diocese_router,
    export_router,
    fund_projects_router,
    members_router,
    notification_router,
    parish_subscriptions_router,
    parishes_router,
    roles_router,
    sacraments_router,
    subscription_payments_router,
    subscription_plan_features_router,
    subscription_plans_router,
    user_invites_router,
    users_router,
    certificates_router,
    sacrament_records_router,
    bulk_communication_router,
    permission_router,
)
from db.session import SessionLocal
from middleware.middleware_manager import (
    setup_middlewares,
    add_middleware_health_endpoint,
)
from services.certificate_service import check_certificates_exist, create_certificates
from services.role_service import check_roles_exist, create_roles
from services.diocese_service import check_dioceses_exist, create_dioceses
from services.parishes_service import check_parishes_exist, create_parishes
from services.subscription_plan_features_service import (
    check_subscription_plan_features_exist,
    create_subscription_plan_features,
)
from services.user_service import check_users_exist, create_users
from services.members_service import check_members_exist, create_members
from services.sacraments_service import check_sacraments_exist, create_sacraments
from services.sacrament_record_service import (
    check_sacrament_records_exist,
    create_sacrament_records,
)
from services.fund_projects_service import (
    check_fund_projects_exist,
    create_fund_projects,
)
from services.collections_service import check_collections_exist, create_collections
from services.attendance_service import (
    check_attendance_records_exist,
    create_attendance_records,
)
from services.subscription_plans_service import (
    check_subscription_plans_exist,
    create_subscription_plans,
)
from services.subscription_plan_feature_pivot_service import (
    check_subscription_plan_feature_pivot_exist,
    create_subscription_plan_feature_pivot,
)
from services.parish_subscription_service import (
    check_parish_subscriptions_exist,
    create_parish_subscriptions,
)
from services.subscription_payment_service import (
    check_parish_subscription_payments_exist,
    create_subscription_payments_for_active_subscriptions,
)
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Running startup lifespan...")
    with SessionLocal() as db:
        try:
            if not check_roles_exist(db):
                create_roles(db)
            if not check_dioceses_exist(db):
                create_dioceses(db)
            if not check_parishes_exist(db):
                create_parishes(db)
            if not check_users_exist(db):
                create_users(db)
            if not check_members_exist(db):
                create_members(db)
            if not check_sacraments_exist(db):
                create_sacraments(db)
            if not check_sacrament_records_exist(db):
                create_sacrament_records(db)
            if not check_fund_projects_exist(db):
                create_fund_projects(db)
            if not check_collections_exist(db):
                create_collections(db)
            if not check_attendance_records_exist(db):
                create_attendance_records(db)
            if not check_subscription_plans_exist(db):
                create_subscription_plans(db)
            if not check_subscription_plan_features_exist(db):
                create_subscription_plan_features(db)
            if not check_subscription_plan_feature_pivot_exist(db):
                create_subscription_plan_feature_pivot(db)
            if not check_parish_subscriptions_exist(db):
                create_parish_subscriptions(db)
            if not check_parish_subscription_payments_exist(db):
                create_subscription_payments_for_active_subscriptions(db)
            if not check_certificates_exist(db):
                create_certificates(db)
            yield
        finally:
            db.close()


app = FastAPI(
    lifespan=lifespan,
    title="iParish cms",
    description="""
    This is a collection of API's for managing church services.

    🚀 Features:
    - Add and manage sacraments
    - Add and manage fund contributions and projects
    - Add and manage church members
    - Add and manage subscriptions
    - Add and manage church attendance
    """,
    version="1.0.0",
    contact={"name": "BCK Ltd"},
)
security = HTTPBearer()

origins = [
    "http://iparish.bck.co.ke",
    "http://127.0.0.1:5173",
    "https://iparish-portal.bck.co.ke",
    "https://iparish-apis.bck.co.ke",
    "https://iparish.bck.co.ke",
]


def get_allowed_origins(origin: str):
    allowed_origins = origins
    if origin.endswith(".iparish.bck.co.ke"):
        return True
    if origin.endswith(".iparish.bck.co.ke"):
        return True
    return origin in allowed_origins


# Setup middleware system
middleware_manager = setup_middlewares(app)

# Add middleware health endpoint
add_middleware_health_endpoint(app, middleware_manager)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router.router, prefix="/user", tags=["USER MANAGEMENT"])

app.include_router(
    permission_router.router, prefix="/permission", tags=["PERMISSION MANAGEMENT"]
)

app.include_router(
    user_invites_router.router, prefix="/user-invites", tags=["USER INVITE MANAGEMENT"]
)

app.include_router(roles_router.router, prefix="/role", tags=["ROLE MANAGEMENT"])

app.include_router(
    diocese_router.router, prefix="/diocese", tags=["DIOCESE MANAGEMENT"]
)

app.include_router(parishes_router.router, prefix="/parish", tags=["PARISH MANAGEMENT"])

app.include_router(members_router.router, prefix="/member", tags=["MEMBER MANAGEMENT"])

app.include_router(
    collections_router.router,
    prefix="/collection",
    tags=["COLLECTION MANAGEMENT"],
)

app.include_router(
    sacraments_router.router,
    prefix="/sacrament",
    tags=["SACRAMENT MANAGEMENT"],
)

app.include_router(
    sacrament_records_router.router,
    prefix="/sacrament-record",
    tags=["SACRAMENT RECORD MANAGEMENT"],
)

app.include_router(
    fund_projects_router.router,
    prefix="/fund-project",
    tags=["FUND PROJECT MANAGEMENT"],
)

app.include_router(
    attendance_router.router,
    prefix="/attendance-record",
    tags=["ATTENDANCE RECORD MANAGEMENT"],
)

app.include_router(
    subscription_plans_router.router,
    prefix="/subscription-plan",
    tags=["SUBSCRIPTION PLAN MANAGEMENT"],
)

app.include_router(
    subscription_plan_features_router.router,
    prefix="/subscription-plan-feature",
    tags=["SUBSCRIPTION PLAN FEATURE MANAGEMENT"],
)

app.include_router(
    parish_subscriptions_router.router,
    prefix="/parish-subscription",
    tags=["PARISH SUBSCRIPTION MANAGEMENT"],
)

app.include_router(
    subscription_payments_router.router,
    prefix="/subscription-payments",
    tags=["SUBSCRIPTION PAYMENTS MANAGEMENT"],
)

app.include_router(
    certificates_router.router,
    prefix="/certificate",
    tags=["CERTIFICATE MANAGEMENT"],
)

app.include_router(
    notification_router.router,
    prefix="/notification",
    tags=["NOTIFICATION MANAGEMENT"],
)

app.include_router(
    bulk_upload_router.router,
    prefix="/bulk-upload",
    tags=["BULK UPLOAD MANAGEMENT"],
)

app.include_router(
    dashboard_analytics_router.router,
    prefix="/dashboard-analytics",
    tags=["DASHBOARD ANALYTICS MANAGEMENT"],
)

app.include_router(
    export_router.router, prefix="/export", tags=["DATA EXPORT MANAGEMENT"]
)

app.include_router(
    bulk_communication_router.router,
    prefix="/communications",
    tags=["BULK COMMUNICATION MANAGEMENT"],
)

app.include_router(
    audit_log_router.router,
    prefix="/audit-log",
    tags=["AUDIT LOG MANAGEMENT"],
)

desc = ""


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_description = f"{desc}\n\nPowered by BCK"

    openapi_schema = get_openapi(
        title="iParish - Backend APIs",
        version="2.1.0",
        description=openapi_description,
        routes=app.routes,
    )

    # Ensure "components" key exists
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
