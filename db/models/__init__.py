from sqlalchemy.orm import configure_mappers

from .diocese import Diocese
from .parish import Parish
from .user import User
from .permission import Permission, UserPermission
from .role import Role
from .subscription_plan import SubscriptionPlan
from .subscription_plan_feature import SubscriptionPlanFeature
from .subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from .parish_subscription import ParishSubscription
from .parish_subscription import ParishSubscriptionChange
from .parish_subscription import SubscriptionPayment
from .attendance import Attendance
from .member import Member
from .audit_log import AuditLog
from .certificate import Certificate
from .collection import Collection
from .fund_project import FundProject
from .login_activity import LoginActivity
from .notification import Notification
from .receipt import Receipt
from .sacrament import Sacrament, SacramentRecord
from .user_invite import InvitedUser


configure_mappers()

__all__ = [
    "Diocese",
    "Parish",
    "User",
    "Permission",
    "UserPermission",
    "Role",
    "SubscriptionPlan",
    "SubscriptionPlanFeature",
    "SubscriptionPlanFeaturePivot",
    "ParishSubscription",
    "ParishSubscriptionChange",
    "SubscriptionPayment",
    "Attendance",
    "Member",
    "AuditLog",
    "Certificate",
    "Collection",
    "FundProject",
    "LoginActivity",
    "Notification",
    "Receipt",
    "Sacrament",
    "SacramentRecord",
    "InvitedUser",
]
