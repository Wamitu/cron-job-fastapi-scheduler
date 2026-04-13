"""
Middleware Manager for iParish CMS

This module provides a centralized way to manage and configure all middlewares
with proper ordering, error handling, and performance optimizations.
"""

from fastapi import FastAPI, Request
from typing import Dict, Any
import time
from log_config import logger

from .audit_log_middleware import AuditLogMiddleware

from .role_middleware import role_middleware
from .feature_middleware import feature_middleware
from .error_handling_middleware import setup_error_handling


class MiddlewareManager:
    """
    Centralized middleware manager that handles:
    - Middleware ordering and execution
    - Error handling and logging
    - Performance monitoring
    - Configuration management
    """

    def __init__(self, app: FastAPI):
        self.app = app
        self.middleware_config = {
            "error_handling": {"enabled": True, "log_level": "error"},
            "audit_log": {
                "enabled": True,
                "exclude_paths": ["/health", "/docs", "/openapi.json"],
            },
            "role_check": {"enabled": True, "cache_duration": 300},  # 5 minutes
            "feature_check": {"enabled": True, "cache_duration": 300},  # 5 minutes
            "performance_monitoring": {"enabled": True, "slow_request_threshold": 2.0},
        }
        self._setup_exception_handlers()
        self._setup_middlewares()

    def _setup_exception_handlers(self):
        """Setup global exception handlers for consistent error responses."""
        # Error handling is now managed by the ErrorHandlingMiddleware
        if self.middleware_config["error_handling"]["enabled"]:
            setup_error_handling(self.app)

    def _setup_middlewares(self):
        """Setup all middlewares in the correct order."""

        # 1. Database session middleware must be first for downstream middlewares
        self._add_database_session_middleware()

        # 2. Performance monitoring middleware (measure entire pipeline)
        if self.middleware_config["performance_monitoring"]["enabled"]:
            self._add_performance_middleware()

        # 3. Audit logging middleware (early to capture all requests)
        if self.middleware_config["audit_log"]["enabled"]:
            self.app.add_middleware(AuditLogMiddleware)

        # 4. Role-based access control middleware
        if self.middleware_config["role_check"]["enabled"]:
            role_middleware(self.app)

        # 5. Feature-based access control middleware
        if self.middleware_config["feature_check"]["enabled"]:
            feature_middleware(self.app)

    def _add_performance_middleware(self):
        """Add performance monitoring middleware."""

        @self.app.middleware("http")
        async def performance_monitoring_middleware(request: Request, call_next):
            start_time = time.time()

            # Add request ID for tracking
            request_id = f"{int(start_time * 1000)}_{id(request)}"
            request.state.request_id = request_id

            try:
                response = await call_next(request)

                process_time = time.time() - start_time
                threshold = self.middleware_config["performance_monitoring"][
                    "slow_request_threshold"
                ]

                # Log performance metrics
                if process_time > threshold:
                    logger.warning(
                        f"Slow request detected: {request.method} {request.url.path} "
                        f"took {process_time:.3f}s (threshold: {threshold}s) "
                        f"[Request ID: {request_id}]"
                    )
                else:
                    logger.debug(
                        f"Request completed: {request.method} {request.url.path} "
                        f"in {process_time:.3f}s [Request ID: {request_id}]"
                    )

                # Add performance headers
                response.headers["X-Process-Time"] = str(process_time)
                response.headers["X-Request-ID"] = request_id

                return response

            except Exception as e:
                process_time = time.time() - start_time
                logger.error(
                    f"Request failed: {request.method} {request.url.path} "
                    f"after {process_time:.3f}s - {e} [Request ID: {request_id}]"
                )
                raise

    def _add_database_session_middleware(self):
        """Add database session middleware if not already present."""

        @self.app.middleware("http")
        async def database_session_middleware(request: Request, call_next):
            # Check if database session is already in request state
            if not hasattr(request.state, "db"):
                from db.session import SessionLocal

                db = SessionLocal()
                request.state.db = db

                try:
                    response = await call_next(request)
                    return response
                finally:
                    db.close()
            else:
                return await call_next(request)

    def configure_middleware(self, middleware_name: str, config: Dict[str, Any]):
        """
        Configure a specific middleware.

        Args:
            middleware_name: Name of the middleware to configure
            config: Configuration dictionary
        """
        if middleware_name in self.middleware_config:
            self.middleware_config[middleware_name].update(config)
            logger.info(f"Updated configuration for {middleware_name}: {config}")
        else:
            logger.warning(f"Unknown middleware: {middleware_name}")

    def get_middleware_status(self) -> Dict[str, Any]:
        """Get the current status and configuration of all middlewares."""
        return {
            "middlewares": self.middleware_config,
            "active_middlewares": [
                name
                for name, config in self.middleware_config.items()
                if config.get("enabled", False)
            ],
        }

    def disable_middleware(self, middleware_name: str):
        """Disable a specific middleware."""
        if middleware_name in self.middleware_config:
            self.middleware_config[middleware_name]["enabled"] = False
            logger.info(f"Disabled middleware: {middleware_name}")
        else:
            logger.warning(f"Unknown middleware: {middleware_name}")

    def enable_middleware(self, middleware_name: str):
        """Enable a specific middleware."""
        if middleware_name in self.middleware_config:
            self.middleware_config[middleware_name]["enabled"] = True
            logger.info(f"Enabled middleware: {middleware_name}")
        else:
            logger.warning(f"Unknown middleware: {middleware_name}")


def setup_middlewares(app: FastAPI) -> MiddlewareManager:
    """
    Setup all middlewares for the FastAPI application.

    Args:
        app: FastAPI application instance

    Returns:
        MiddlewareManager instance for further configuration
    """
    manager = MiddlewareManager(app)
    logger.info("Middleware system initialized successfully")
    return manager


# Health check endpoint for middleware status
def add_middleware_health_endpoint(app: FastAPI, manager: MiddlewareManager):
    """Add a health check endpoint that shows middleware status."""

    @app.get("/middleware/health", tags=["System Health"])
    async def middleware_health():
        """Get middleware system health status."""
        return {
            "status": "healthy",
            "middlewares": manager.get_middleware_status(),
            "timestamp": time.time(),
        }
