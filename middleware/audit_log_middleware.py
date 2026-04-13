import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request
from db.session import SessionLocal
from db.models.audit_log import AuditLog
from log_config import logger
import json
import asyncio
from typing import Optional, Dict, Any
from services.auth_service import get_current_user, decode_jwt_token
from sqlalchemy.exc import SQLAlchemyError


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log audit entries for every action in the system.
    All HTTP methods are logged except HEAD and OPTIONS.
    Captures before_data and after_data to provide a full audit trail.
    For login responses, extracts the user identity from the returned access token.
    """

    # Skip non-meaningful browser/tooling methods
    EXCLUDED_METHODS = {"HEAD", "OPTIONS"}

    # Map HTTP methods to human-readable action types
    ACTION_MAP = {
        "GET": "READ",
        "POST": "CREATE",
        "PUT": "UPDATE",
        "PATCH": "UPDATE",
        "DELETE": "DELETE",
    }

    # Sensitive fields to redact from request bodies
    SENSITIVE_FIELDS = {
        "password", "old_password", "new_password", "confirm_password",
        "access_token", "refresh_token", "secret", "api_key", "token",
        "hashed_password",
    }

    # Maximum response body size to store (5 KB)
    MAX_RESPONSE_BODY_SIZE = 5000

    # Paths to exclude from audit logging
    EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXCLUDED_PATHS or request.method in self.EXCLUDED_METHODS:
            return await call_next(request)

        # time.monotonic() is safe across all Python versions — no event-loop dependency
        start_time = time.monotonic()

        user_info: Dict[str, Optional[str]] = {}
        request_body_str: Optional[str] = None

        # --- Pre-request: capture user context and request body ---
        try:
            user_info = await self._extract_user_info(request)
        except Exception as e:
            logger.warning(f"Audit: failed to extract user info: {e}")

        # Only read the body for write operations — GET responses can be very large
        is_write = request.method in ("POST", "PUT", "PATCH", "DELETE")
        if is_write:
            try:
                request_body_str = await self._process_request_body(request)
            except Exception as e:
                logger.warning(f"Audit: failed to read request body: {e}")

        # --- Process the actual request ---
        response = await call_next(request)
        status_code = response.status_code

        # --- Post-request: capture response body and schedule DB write ---
        try:
            response_body_bytes, response_body_str = await self._read_response_body(response)

            # For unauthenticated write requests that return an access_token (e.g. login),
            # decode the token so the audit entry is attributed to the correct user.
            if not user_info and is_write and status_code < 300:
                user_info = self._extract_user_from_token_response(response_body_str)

            before_data: Optional[str] = None
            if request.method in ("PUT", "PATCH", "DELETE"):
                before_data = request_body_str

            after_data: Optional[str] = None
            if is_write and status_code < 300:
                after_data = response_body_str

            asyncio.create_task(
                self._save_audit_log_async(
                    user_info=user_info,
                    request=request,
                    status_code=status_code,
                    request_body_str=request_body_str,
                    response_body_str=response_body_str if is_write else None,
                    before_data=before_data,
                    after_data=after_data,
                    start_time=start_time,
                )
            )

            # Rebuild response (body_iterator is exhausted; must reconstruct)
            new_headers = dict(response.headers)
            new_headers.pop("content-length", None)
            new_headers.pop("Content-Length", None)
            new_headers.pop("transfer-encoding", None)
            new_headers.pop("Transfer-Encoding", None)

            return Response(
                content=response_body_bytes or b"",
                status_code=status_code,
                headers=new_headers,
                media_type=response.media_type,
            )

        except Exception as e:
            logger.error(f"Audit: post-request capture failed: {e}")
            return Response(status_code=status_code)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    async def _extract_user_info(self, request: Request) -> Dict[str, Optional[str]]:
        """Decode the JWT and return user/parish/diocese IDs. Uses its own DB session."""
        db = SessionLocal()
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or " " not in auth_header:
                return {}

            token = auth_header.split(" ")[1]
            if not token:
                return {}

            current_user = await get_current_user(db=db, token=token)
            if not current_user:
                return {}

            return {
                "user_id": str(current_user.id),
                "parish_id": str(current_user.parish_id) if current_user.parish_id else None,
                "diocese_id": str(current_user.diocese_id) if current_user.diocese_id else None,
            }
        except Exception as e:
            logger.debug(f"Audit: user info extraction error: {e}")
            return {}
        finally:
            db.close()

    def _extract_user_from_token_response(
        self, response_body_str: Optional[str]
    ) -> Dict[str, Optional[str]]:
        """
        For unauthenticated requests that return an access_token (e.g. login),
        decode the token to attribute the audit log entry to the correct user.
        """
        if not response_body_str:
            return {}
        try:
            body = json.loads(response_body_str)
            access_token = body.get("access_token")
            if not access_token:
                return {}

            payload = decode_jwt_token(access_token)
            user_id = payload.get("sub")
            if not user_id:
                return {}

            db = SessionLocal()
            try:
                from services.user_service import get_user_by_id
                user = get_user_by_id(db, id=user_id)
                if user:
                    return {
                        "user_id": str(user.id),
                        "parish_id": str(user.parish_id) if user.parish_id else None,
                        "diocese_id": str(user.diocese_id) if user.diocese_id else None,
                    }
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Audit: could not extract user from token response: {e}")
        return {}

    async def _process_request_body(self, request: Request) -> Optional[str]:
        """Read the request body, parse JSON, and redact sensitive fields."""
        try:
            content_type = request.headers.get("content-type", "")
            # Skip multipart bodies (file uploads) — they can be very large
            if "multipart/form-data" in content_type:
                return "[multipart/form-data — body not captured]"

            body_bytes = await request.body()
            if not body_bytes:
                return None

            request_body_str = body_bytes.decode("utf-8")
            if not request_body_str:
                return None

            try:
                body_json = json.loads(request_body_str)
                if isinstance(body_json, dict):
                    return json.dumps(self._redact_sensitive_fields(body_json))
            except json.JSONDecodeError:
                pass  # Not JSON — return raw string

            return request_body_str
        except Exception as e:
            logger.debug(f"Audit: request body processing error: {e}")
            return None

    async def _read_response_body(self, response) -> tuple:
        """Consume the response body iterator and return (bytes, truncated_str)."""
        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            log_str = body.decode("utf-8", errors="ignore")[: self.MAX_RESPONSE_BODY_SIZE]
            return body, log_str
        except Exception as e:
            logger.debug(f"Audit: response body read error: {e}")
            return b"", None

    def _redact_sensitive_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact sensitive fields from a dictionary."""
        if not isinstance(data, dict):
            return data

        redacted = {}
        for key, value in data.items():
            if key.lower() in self.SENSITIVE_FIELDS:
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self._redact_sensitive_fields(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_sensitive_fields(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted

    async def _save_audit_log_async(
        self,
        user_info: Dict[str, Optional[str]],
        request: Request,
        status_code: int,
        request_body_str: Optional[str],
        response_body_str: Optional[str],
        before_data: Optional[str],
        after_data: Optional[str],
        start_time: float,
    ):
        """Persist the audit log entry to the database (runs as a background task)."""
        db = SessionLocal()
        try:
            # time.monotonic() matches how start_time was captured — no event-loop needed
            processing_time = time.monotonic() - start_time
            action = self.ACTION_MAP.get(request.method, request.method)

            audit_entry = AuditLog(
                user_id=user_info.get("user_id"),
                diocese_id=user_info.get("diocese_id"),
                parish_id=user_info.get("parish_id"),
                method=request.method,
                path=request.url.path,
                status_code=str(status_code),
                ip_address=request.client.host if request.client else None,
                request_body=request_body_str,
                response_body=response_body_str,
                before_data=before_data,
                after_data=after_data,
            )

            db.add(audit_entry)
            db.commit()

            logger.info(
                f"Audit [{action}] {request.method} {request.url.path} | "
                f"User: {user_info.get('user_id')} | "
                f"Parish: {user_info.get('parish_id')} | "
                f"Status: {status_code} | "
                f"Time: {processing_time:.3f}s"
            )

        except SQLAlchemyError as db_err:
            db.rollback()
            logger.error(f"Audit: DB error while saving log: {db_err}")
        except Exception as e:
            logger.error(f"Audit: unexpected error while saving log: {e}")
        finally:
            db.close()
