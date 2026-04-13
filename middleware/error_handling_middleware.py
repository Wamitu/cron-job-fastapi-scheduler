"""
Error Handling Middleware for iParish CMS

This module provides comprehensive error handling, logging, and response formatting
for all types of errors that can occur in the application.
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import ValidationError
from typing import Dict, Any, Optional
import traceback
import time
from log_config import logger


class ErrorHandlingMiddleware:
    """
    Comprehensive error handling middleware that:
    - Catches and formats all types of errors
    - Provides detailed logging for debugging
    - Returns consistent error responses
    - Handles database errors gracefully
    - Provides security by not exposing sensitive information
    """
    
    def __init__(self, app):
        self.app = app
        self._setup_error_handlers()
    
    def _setup_error_handlers(self):
        """Setup all error handlers."""
        
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return await self._handle_http_exception(request, exc)
        
        @self.app.exception_handler(ValidationError)
        async def validation_exception_handler(request: Request, exc: ValidationError):
            return await self._handle_validation_error(request, exc)
        
        @self.app.exception_handler(IntegrityError)
        async def integrity_error_handler(request: Request, exc: IntegrityError):
            return await self._handle_database_error(request, exc, "integrity")
        
        @self.app.exception_handler(OperationalError)
        async def operational_error_handler(request: Request, exc: OperationalError):
            return await self._handle_database_error(request, exc, "operational")
        
        @self.app.exception_handler(SQLAlchemyError)
        async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
            return await self._handle_database_error(request, exc, "general")
        
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            return await self._handle_general_exception(request, exc)
    
    async def _handle_http_exception(self, request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions with proper logging and formatting."""
        
        error_data = {
            "error": "HTTP Exception",
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
            "timestamp": time.time()
        }
        
        # Log based on status code severity
        if exc.status_code >= 500:
            logger.error(f"Server error: {exc.status_code} - {exc.detail} for {request.method} {request.url.path}")
        elif exc.status_code >= 400:
            logger.warning(f"Client error: {exc.status_code} - {exc.detail} for {request.method} {request.url.path}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_data
        )
    
    async def _handle_validation_error(self, request: Request, exc: ValidationError) -> JSONResponse:
        """Handle Pydantic validation errors."""
        
        error_details = []
        for error in exc.errors():
            error_details.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        error_data = {
            "error": "Validation Error",
            "status_code": 422,
            "detail": "Request validation failed",
            "validation_errors": error_details,
            "path": request.url.path,
            "method": request.method,
            "timestamp": time.time()
        }
        
        logger.warning(f"Validation error for {request.method} {request.url.path}: {error_details}")
        
        return JSONResponse(
            status_code=422,
            content=error_data
        )
    
    async def _handle_database_error(
        self, request: Request, exc: SQLAlchemyError, error_type: str
    ) -> JSONResponse:
        """Handle database-related errors."""
        
        # Log the full error for debugging
        logger.error(f"Database {error_type} error for {request.method} {request.url.path}: {exc}")
        
        # Determine user-friendly message based on error type
        if error_type == "integrity":
            detail = "Data integrity constraint violation. The operation conflicts with existing data."
        elif error_type == "operational":
            detail = "Database connection or operation failed. Please try again later."
        else:
            detail = "A database error occurred. Please try again later."
        
        error_data = {
            "error": f"Database {error_type.title()} Error",
            "status_code": 500,
            "detail": detail,
            "path": request.url.path,
            "method": request.method,
            "timestamp": time.time()
        }
        
        return JSONResponse(
            status_code=500,
            content=error_data
        )
    
    async def _handle_general_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        
        # Log the full error with stack trace for debugging
        logger.error(
            f"Unexpected error for {request.method} {request.url.path}: {exc}\n"
            f"Stack trace: {traceback.format_exc()}"
        )
        
        error_data = {
            "error": "Internal Server Error",
            "status_code": 500,
            "detail": "An unexpected error occurred. Please try again later.",
            "path": request.url.path,
            "method": request.method,
            "timestamp": time.time()
        }
        
        return JSONResponse(
            status_code=500,
            content=error_data
        )


def setup_error_handling(app) -> ErrorHandlingMiddleware:
    """
    Setup comprehensive error handling for the FastAPI application.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        ErrorHandlingMiddleware instance
    """
    return ErrorHandlingMiddleware(app)


# Utility functions for custom error responses
def create_error_response(
    status_code: int,
    detail: str,
    error_type: str = "Error",
    additional_data: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        status_code: HTTP status code
        detail: Error message
        error_type: Type of error
        additional_data: Additional data to include in response
        
    Returns:
        JSONResponse with error data
    """
    error_data = {
        "error": error_type,
        "status_code": status_code,
        "detail": detail,
        "timestamp": time.time()
    }
    
    if additional_data:
        error_data.update(additional_data)
    
    return JSONResponse(
        status_code=status_code,
        content=error_data
    )


def log_security_event(
    request: Request,
    event_type: str,
    details: str,
    severity: str = "warning"
):
    """
    Log security-related events.
    
    Args:
        request: FastAPI request object
        event_type: Type of security event
        details: Event details
        severity: Log severity level
    """
    log_data = {
        "event_type": event_type,
        "details": details,
        "path": request.url.path,
        "method": request.method,
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "timestamp": time.time()
    }
    
    if severity == "error":
        logger.error(f"Security event: {event_type} - {details}", extra=log_data)
    elif severity == "warning":
        logger.warning(f"Security event: {event_type} - {details}", extra=log_data)
    else:
        logger.info(f"Security event: {event_type} - {details}", extra=log_data)
