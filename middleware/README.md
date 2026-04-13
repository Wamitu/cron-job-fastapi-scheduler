# iParish CMS Middleware System

This directory contains the comprehensive middleware system for the iParish CMS FastAPI backend. The middleware system provides authentication, authorization, audit logging, error handling, and performance monitoring.

## Architecture Overview

The middleware system is designed with the following principles:

- **Modularity**: Each middleware has a single responsibility
- **Performance**: Optimized for minimal overhead
- **Security**: Comprehensive error handling and audit logging
- **Maintainability**: Clear separation of concerns and extensive documentation

## Middleware Components

### 1. Middleware Manager (`middleware_manager.py`)

The central orchestrator that manages all middlewares with proper ordering and configuration.

**Features:**

- Centralized configuration management
- Proper middleware ordering
- Performance monitoring
- Health check endpoints
- Dynamic middleware enabling/disabling

### 2. Audit Log Middleware (`audit_log_middleware.py`)

Comprehensive audit logging for all API requests and responses.

**Features:**

- Request/response logging with sensitive data redaction
- User identification and parish tracking
- Asynchronous logging to prevent performance impact
- Configurable exclusion paths
- Performance timing

**Configuration:**

```python
{
    "enabled": True,
    "exclude_paths": ["/health", "/docs", "/openapi.json"],
    "max_response_size": 5000,
    "sensitive_fields": ["password", "token", "secret"]
}
```

### 3. Role Middleware (`role_middleware.py`)

Role-based access control (RBAC) for API endpoints.

**Features:**

- Role-based authorization
- SysAdmin bypass functionality
- Parish-specific access control for priests
- Comprehensive error handling
- Detailed logging

**Usage:**

```python
@require_roles_by_titles("Priest", "Admin")
async def protected_endpoint():
    pass
```

### 4. Feature Middleware (`feature_middleware.py`)

Subscription-based feature access control.

**Features:**

- Feature-based authorization
- Subscription plan validation
- Active subscription checking
- SysAdmin bypass
- Optimized database queries

**Usage:**

```python
@require_feature("advanced_analytics")
async def analytics_endpoint():
    pass
```

### 5. Error Handling Middleware (`error_handling_middleware.py`)

Comprehensive error handling and response formatting.

**Features:**

- Standardized error responses
- Security-focused error messages
- Detailed logging for debugging
- Database error handling
- Validation error formatting

## Middleware Execution Order

The middlewares are executed in the following order to ensure proper functionality:

1. **Performance Monitoring** - Measures request timing
2. **Audit Logging** - Captures all requests early
3. **Role Checking** - Validates user roles
4. **Feature Checking** - Validates subscription features
5. **Database Session** - Ensures database connectivity
6. **Error Handling** - Catches and formats all errors

## Configuration

### Environment Variables

```bash
# Middleware configuration
MIDDLEWARE_AUDIT_ENABLED=true
MIDDLEWARE_ROLE_CHECK_ENABLED=true
MIDDLEWARE_FEATURE_CHECK_ENABLED=true
MIDDLEWARE_PERFORMANCE_MONITORING_ENABLED=true
MIDDLEWARE_SLOW_REQUEST_THRESHOLD=2.0
```

### Runtime Configuration

```python
# Configure middleware at runtime
middleware_manager.configure_middleware("audit_log", {
    "exclude_paths": ["/health", "/docs", "/metrics"]
})

# Disable specific middleware
middleware_manager.disable_middleware("feature_check")

# Enable middleware
middleware_manager.enable_middleware("audit_log")
```

## Usage Examples

### Basic Setup

```python
from fastapi import FastAPI
from middleware.middleware_manager import setup_middlewares

app = FastAPI()
middleware_manager = setup_middlewares(app)
```

### Custom Middleware Configuration

```python
# Configure performance monitoring
middleware_manager.configure_middleware("performance_monitoring", {
    "slow_request_threshold": 1.5,  # 1.5 seconds
    "enabled": True
})

# Configure audit logging
middleware_manager.configure_middleware("audit_log", {
    "exclude_paths": ["/health", "/docs", "/metrics", "/favicon.ico"],
    "max_response_size": 10000
})
```

### Health Check

```python
# Access middleware health status
GET /middleware/health

# Response
{
    "status": "healthy",
    "middlewares": {
        "audit_log": {"enabled": true},
        "role_check": {"enabled": true},
        "feature_check": {"enabled": true},
        "performance_monitoring": {"enabled": true}
    },
    "timestamp": 1640995200.0
}
```

## Security Features

### Audit Logging

- All requests are logged with user identification
- Sensitive fields are automatically redacted
- IP addresses and user agents are tracked
- Response times are monitored

### Role-Based Access Control

- Hierarchical role system
- Parish-specific access for priests
- SysAdmin bypass for system operations
- Comprehensive permission checking

### Feature-Based Access Control

- Subscription plan validation
- Feature availability checking
- Active subscription verification
- Graceful degradation for missing features

### Error Handling

- No sensitive information in error responses
- Detailed logging for debugging
- Consistent error response format
- Security event logging

## Performance Optimizations

### Database Queries

- Optimized joins and eager loading
- Caching for frequently accessed data
- Minimal database calls per request

### Asynchronous Operations

- Non-blocking audit logging
- Async database operations
- Concurrent request processing

### Memory Management

- Limited response body logging
- Efficient data structures
- Proper resource cleanup

## Monitoring and Debugging

### Logging

All middlewares provide comprehensive logging at different levels:

- `DEBUG`: Detailed operation information
- `INFO`: Normal operation events
- `WARNING`: Potential issues or access denials
- `ERROR`: System errors and failures

### Performance Metrics

- Request processing times
- Slow request identification
- Database query performance
- Memory usage tracking

### Health Checks

- Middleware status monitoring
- Configuration validation
- System health reporting

## Best Practices

### Development

1. Always use the middleware decorators for protected endpoints
2. Test with different user roles and subscription levels
3. Monitor performance impact of new middlewares
4. Use proper error handling in custom middlewares

### Production

1. Monitor middleware performance metrics
2. Regularly review audit logs for security issues
3. Keep middleware configurations up to date
4. Use health checks for system monitoring

### Security

1. Regularly audit user permissions
2. Monitor for suspicious access patterns
3. Keep sensitive data redaction rules updated
4. Review error logs for potential security issues

## Troubleshooting

### Common Issues

#### Middleware Not Working

- Check if middleware is enabled in configuration
- Verify middleware order in setup
- Check logs for initialization errors

#### Performance Issues

- Monitor slow request logs
- Check database query performance
- Review middleware configuration

#### Access Denied Errors

- Verify user roles and permissions
- Check subscription status
- Review feature availability

### Debug Mode

Enable debug logging for detailed middleware information:

```python
import logging
logging.getLogger("middleware").setLevel(logging.DEBUG)
```

## Contributing

When adding new middlewares:

1. Follow the existing patterns and structure
2. Add comprehensive error handling
3. Include performance monitoring
4. Update documentation
5. Add appropriate tests
6. Consider security implications

## License

This middleware system is part of the iParish CMS project and follows the same licensing terms.

## Visual representation

============================================================
iParish CMS - Middleware Request Flow
============================================================

Incoming HTTP Request
│
▼
+----------------------------+
| Database Session Middleware|
| - Creates request.state.db |
| - Ensures DB session close |
+----------------------------+
│
▼
+--------------------------------+
| Performance Monitoring Middleware |
| - Start timer |
| - Assign request_id |
| - Log request duration |
| - Add X-Request-ID header |
+--------------------------------+
│
▼
+-------------------------+
| Audit Logging Middleware|
| - Logs request/response |
| - Skips excluded paths |
+-------------------------+
│
▼
+-------------------------+
| Role Middleware |
| - Validates token/user |
| - Checks user role |
| - Special cases: |
| _ SysAdmin → bypass |
| _ Priest → parish_id |
| \* Bishop → diocese |
+-------------------------+
│
▼
+-------------------------+
| Feature Middleware |
| - Checks feature flags |
| - Restricts routes if |
| feature is disabled |
+-------------------------+
│
▼
+-------------------------+
| Route Handler |
| - Executes endpoint |
| - Can access: |
| request.state.db |
| request.state.user |
| request.state.role |
+-------------------------+
│
▼
+-------------------------+
| Performance Monitoring |
| - Stop timer |
| - Add X-Process-Time |
+-------------------------+
│
▼
Outgoing HTTP Response
│
▼
+-------------------------+
| Error Handling Middleware|
| - Catches exceptions |
| - Returns JSONResponse |
| - Logs errors |
+-------------------------+

============================================================
Legend:

- request.state.db → SQLAlchemy session
- request.state.user → Authenticated user
- request.state.role → Role info/permissions
- # request.state.request_id → Unique ID per request
