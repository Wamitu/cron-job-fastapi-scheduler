from datetime import datetime, timedelta
from typing import Callable, Optional
from uuid import UUID
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import ExpiredSignatureError, PyJWTError
from sqlalchemy.orm import Session
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError as PyJWTError
from db.models.parish import Parish
from db.models.parish_subscription import ParishSubscription
from db.models.role import Role
from db.models.subscription_plan import SubscriptionPlan
from db.models.subscription_plan_feature_pivot import SubscriptionPlanFeaturePivot
from db.models.user import User
from db.session import get_db
from log_config import logger

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

SECRET_KEY = "my-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 360


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    """
    logger.debug("Hashing password!")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a hashed one!
    """
    logger.debug("Verifying password!")
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


def create_jwt_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT token with an optional expiration delta!
    """
    logger.debug("Creating JWT token!")
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info("JWT token generated!")
    return token


def decode_jwt_token(token: str) -> dict:
    """
    Decode and verify a JWT token. Raise HTTP 401 if invalid or expired!
    """
    logger.debug("Decoding JWT token!")
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        logger.warning("Token expired!")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired!",
        )
    except PyJWTError:
        logger.error("Invalid token or signature!")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token or signature!",
        )


# get current logged in user
async def get_current_user(
    request: Request = None,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
):
    """
    Extract the current authenticated user from JWT token.
    Works both as a FastAPI dependency and middleware helper.
    """
    from services.user_service import get_user_by_id

    logger.debug("Authenticating current user from token!")

    # If called from middleware, token is passed explicitly
    if request and not token:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header!",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = auth_header.split(" ", 1)[1]

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials!",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_jwt_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("Token missing subject claim!")
            raise credentials_exception
    except PyJWTError:
        logger.warning("Token decoding failed!")
        raise credentials_exception

    user = get_user_by_id(db, id=user_id)
    if user is None:
        logger.warning("User not found from token!")
        raise credentials_exception

    logger.info("User authenticated successfully!")
    return user
