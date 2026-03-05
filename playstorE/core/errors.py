"""
Unified Error Handling for pLayStorE Platform.

Provides:
- Custom exception hierarchy
- Standardized error responses
- Error logging and tracking
- User-friendly error messages

Usage:
    from playstorE.core.errors import AltStoreError, ValidationError
    
    @app.get("/endpoint")
    async def endpoint():
        raise ValidationError("Invalid input")
"""

import logging
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """Standardized error codes"""
    # General errors (1000-1999)
    INTERNAL_ERROR = 1000
    INVALID_REQUEST = 1001
    NOT_FOUND = 1002
    UNAUTHORIZED = 1003
    FORBIDDEN = 1004
    RATE_LIMITED = 1005

    # Validation errors (2000-2999)
    VALIDATION_ERROR = 2000
    SCHEMA_ERROR = 2001
    MISSING_FIELD = 2002
    INVALID_FORMAT = 2003

    # Security errors (3000-3999)
    SECURITY_ERROR = 3000
    AUTHENTICATION_FAILED = 3001
    AUTHORIZATION_FAILED = 3002
    SIGNATURE_INVALID = 3003
    TOKEN_EXPIRED = 3004
    PATH_TRAVERSAL = 3005
    XSS_ATTEMPT = 3006

    # Build errors (4000-4999)
    BUILD_ERROR = 4000
    BUILD_FAILED = 4001
    BUILD_TIMEOUT = 4002
    REPRODUCIBILITY_FAILED = 4003

    # Storage errors (5000-5999)
    STORAGE_ERROR = 5000
    CAPSULE_ERROR = 5001
    CAPSULE_INVALID = 5002
    CAPSULE_NOT_FOUND = 5003
    STORAGE_FULL = 5004

    # GitHub errors (6000-6999)
    GITHUB_ERROR = 6000
    GITHUB_RATE_LIMITED = 6001
    GITHUB_NOT_FOUND = 6002
    GITHUB_AUTH_FAILED = 6003

    # Execution errors (7000-7999)
    EXECUTION_ERROR = 7000
    EXECUTION_FAILED = 7001
    EXECUTION_TIMEOUT = 7002
    SANDBOX_ERROR = 7003
    WASM_ERROR = 7004


class AltStoreError(Exception):
    """
    Base exception for all AltStore errors.

    Attributes:
        message: Human-readable error message
        error_code: Standardized error code
        details: Additional error details
        should_log: Whether to log this error
        log_level: Log level for this error
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        should_log: bool = True,
        log_level: int = logging.ERROR
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.should_log = should_log
        self.log_level = log_level
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response"""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.message,
                "type": self.__class__.__name__,
                "details": self.details if self.details else None,
                "timestamp": self.timestamp.isoformat() + "Z"
            }
        }

    def __str__(self) -> str:
        return f"[{self.error_code.name}] {self.message}"


# Specific exception classes
class ValidationError(AltStoreError):
    """Raised when input validation fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
            log_level=logging.WARNING
        )


class SecurityError(AltStoreError):
    """Raised when a security violation is detected"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.SECURITY_ERROR,
            details=details,
            should_log=True,
            log_level=logging.WARNING
        )


class AuthenticationError(AltStoreError):
    """Raised when authentication fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_FAILED,
            details=details,
            should_log=True,
            log_level=logging.INFO
        )


class AuthorizationError(AltStoreError):
    """Raised when authorization fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHORIZATION_FAILED,
            details=details,
            should_log=True,
            log_level=logging.INFO
        )


class NotFoundError(AltStoreError):
    """Raised when a resource is not found"""
    def __init__(self, message: str, resource_type: str = None):
        details = {"resource_type": resource_type} if resource_type else {}
        super().__init__(
            message=message,
            error_code=ErrorCode.NOT_FOUND,
            details=details,
            log_level=logging.INFO
        )


class BuildError(AltStoreError):
    """Raised when a build operation fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.BUILD_ERROR,
            details=details,
            should_log=True,
            log_level=logging.ERROR
        )


class CapsuleError(AltStoreError):
    """Raised when a capsule operation fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.CAPSULE_ERROR,
            details=details,
            should_log=True,
            log_level=logging.ERROR
        )


class CapsuleIntegrityError(CapsuleError):
    """Raised when capsule integrity verification fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            details={"integrity_failure": True, **(details or {})}
        )


class GitHubError(AltStoreError):
    """Raised when GitHub API operation fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.GITHUB_ERROR,
            details=details,
            log_level=logging.ERROR
        )


class RateLimitError(AltStoreError):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str, retry_after: int = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMITED,
            details=details,
            log_level=logging.INFO
        )


class ExecutionError(AltStoreError):
    """Raised when application execution fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.EXECUTION_ERROR,
            details=details,
            should_log=True,
            log_level=logging.ERROR
        )


class PathTraversalError(SecurityError):
    """Raised when path traversal is detected"""
    def __init__(self, message: str, path: str = None):
        details = {"path": path} if path else {}
        super().__init__(
            message=message,
            details={"attack_type": "path_traversal", **details}
        )


class XSSAttemptError(SecurityError):
    """Raised when XSS attempt is detected"""
    def __init__(self, message: str, payload: str = None):
        details = {"payload": payload} if payload else {}
        super().__init__(
            message=message,
            details={"attack_type": "xss", **details}
        )


# Error handler for FastAPI
def setup_error_handlers(app):
    """
    Set up global error handlers for FastAPI application.

    Usage:
        from playstorE.core.errors import setup_error_handlers
        setup_error_handlers(app)
    """

    @app.exception_handler(AltStoreError)
    async def altstore_error_handler(request: Request, exc: AltStoreError):
        """Handle AltStore custom exceptions"""
        # Log the error
        if exc.should_log:
            logger.log(
                exc.log_level,
                f"AltStoreError | code={exc.error_code.name} | "
                f"message={exc.message} | path={request.url.path} | "
                f"method={request.method}"
            )

        return JSONResponse(
            status_code=_get_status_code(exc.error_code),
            content=exc.to_dict()
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle FastAPI HTTP exceptions"""
        logger.info(
            f"HTTPException | status={exc.status_code} | "
            f"detail={exc.detail} | path={request.url.path}"
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.status_code,
                    "message": str(exc.detail),
                    "type": "HTTPException",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors"""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(x) for x in error.get("loc", [])),
                "message": error.get("msg"),
                "type": error.get("type")
            })

        logger.warning(
            f"RequestValidationError | path={request.url.path} | "
            f"errors={len(errors)}"
        )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": "Request validation failed",
                    "type": "RequestValidationError",
                    "details": {"errors": errors},
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError):
        """Handle Pydantic validation errors"""
        try:
            errors = exc.errors()
        except Exception:
            errors = [{"message": str(exc)}]

        logger.warning(
            f"PydanticValidationError | path={request.url.path} | "
            f"errors={len(errors)}"
        )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": ErrorCode.SCHEMA_ERROR.value,
                    "message": "Data validation failed",
                    "type": "PydanticValidationError",
                    "details": {"errors": errors},
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions"""
        # Log full traceback for debugging
        logger.error(
            f"UnhandledException | type={type(exc).__name__} | "
            f"message={str(exc)} | path={request.url.path} | "
            f"traceback={traceback.format_exc()}"
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "An internal error occurred",
                    "type": type(exc).__name__,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
        )


def _get_status_code(error_code: ErrorCode) -> int:
    """Map error code to HTTP status code"""
    mapping = {
        ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
        ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ErrorCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
        ErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
        ErrorCode.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
        ErrorCode.VALIDATION_ERROR: status.HTTP_400_BAD_REQUEST,
        ErrorCode.SCHEMA_ERROR: status.HTTP_400_BAD_REQUEST,
        ErrorCode.MISSING_FIELD: status.HTTP_400_BAD_REQUEST,
        ErrorCode.INVALID_FORMAT: status.HTTP_400_BAD_REQUEST,
        ErrorCode.SECURITY_ERROR: status.HTTP_403_FORBIDDEN,
        ErrorCode.AUTHENTICATION_FAILED: status.HTTP_401_UNAUTHORIZED,
        ErrorCode.AUTHORIZATION_FAILED: status.HTTP_403_FORBIDDEN,
        ErrorCode.SIGNATURE_INVALID: status.HTTP_403_FORBIDDEN,
        ErrorCode.TOKEN_EXPIRED: status.HTTP_401_UNAUTHORIZED,
        ErrorCode.PATH_TRAVERSAL: status.HTTP_403_FORBIDDEN,
        ErrorCode.XSS_ATTEMPT: status.HTTP_403_FORBIDDEN,
        ErrorCode.BUILD_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.BUILD_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.BUILD_TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
        ErrorCode.REPRODUCIBILITY_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.STORAGE_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.CAPSULE_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.CAPSULE_INVALID: status.HTTP_400_BAD_REQUEST,
        ErrorCode.CAPSULE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ErrorCode.STORAGE_FULL: status.HTTP_507_INSUFFICIENT_STORAGE,
        ErrorCode.GITHUB_ERROR: status.HTTP_502_BAD_GATEWAY,
        ErrorCode.GITHUB_RATE_LIMITED: status.HTTP_502_BAD_GATEWAY,
        ErrorCode.GITHUB_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ErrorCode.GITHUB_AUTH_FAILED: status.HTTP_502_BAD_GATEWAY,
        ErrorCode.EXECUTION_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.EXECUTION_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.EXECUTION_TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
        ErrorCode.SANDBOX_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.WASM_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    return mapping.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


# Utility functions
def raise_if(condition: bool, exception: AltStoreError):
    """Raise exception if condition is true"""
    if condition:
        raise exception


def validate_not_none(value: Any, field_name: str):
    """Validate that a value is not None"""
    if value is None:
        raise ValidationError(f"{field_name} cannot be null")
    return value


def validate_not_empty(value: str, field_name: str):
    """Validate that a string is not empty"""
    if not value or not value.strip():
        raise ValidationError(f"{field_name} cannot be empty")
    return value


def validate_length(value: str, field_name: str, min_len: int = None, max_len: int = None):
    """Validate string length"""
    if min_len is not None and len(value) < min_len:
        raise ValidationError(f"{field_name} must be at least {min_len} characters")
    if max_len is not None and len(value) > max_len:
        raise ValidationError(f"{field_name} must be at most {max_len} characters")
    return value


def validate_range(value: int, field_name: str, min_val: int = None, max_val: int = None):
    """Validate numeric range"""
    if min_val is not None and value < min_val:
        raise ValidationError(f"{field_name} must be at least {min_val}")
    if max_val is not None and value > max_val:
        raise ValidationError(f"{field_name} must be at most {max_val}")
    return value
