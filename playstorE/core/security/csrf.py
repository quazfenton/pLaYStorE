"""
CSRF Protection Middleware for pLayStorE Platform.

Provides:
- CSRF token generation and validation
- Double-submit cookie pattern
- Origin/Referer header validation
- CSRF-protected route decorator

Based on OWASP CSRF prevention recommendations.

Usage:
    from playstorE.core.security.csrf import CSRFMiddleware, csrf_protect
    
    app.add_middleware(CSRFMiddleware)
    
    @app.post("/install")
    @csrf_protect
    async def install_endpoint(request: Request):
        ...
"""

import os
import secrets
import hashlib
import hmac
import logging
from typing import Optional, Set, List
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class CSRFConfig:
    """CSRF protection configuration"""

    def __init__(
        self,
        secret_key: str = None,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        token_lifetime_seconds: int = 3600,
        exempt_paths: Set[str] = None,
        exempt_methods: Set[str] = None,
        validate_origin: bool = True,
        allowed_origins: List[str] = None,
    ):
        """
        Initialize CSRF configuration.

        Args:
            secret_key: Secret key for token generation (auto-generated if not provided)
            cookie_name: Name of the CSRF cookie
            header_name: Name of the CSRF header
            token_lifetime_seconds: Token validity period
            exempt_paths: Paths exempt from CSRF protection
            exempt_methods: HTTP methods exempt from CSRF protection
            validate_origin: Whether to validate Origin/Referer headers
            allowed_origins: List of allowed origins for origin validation
        """
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.token_lifetime_seconds = token_lifetime_seconds
        self.exempt_paths = exempt_paths or {"/api/health", "/health", "/docs", "/redoc", "/openapi.json"}
        self.exempt_methods = exempt_methods or {"GET", "HEAD", "OPTIONS"}
        self.validate_origin = validate_origin
        self.allowed_origins = allowed_origins or []


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware.

    Implements the Double-Submit Cookie pattern with Origin validation:
    1. Server sets a CSRF token cookie
    2. Client must send the token in a custom header
    3. Server validates the header matches the cookie
    4. Server also validates Origin/Referer headers

    This provides defense in depth against CSRF attacks.
    """

    def __init__(self, app: ASGIApp, config: CSRFConfig = None):
        super().__init__(app)
        self.config = config or CSRFConfig()
        self.csrf_logger = logging.getLogger("altstore.csrf")

    async def dispatch(self, request: Request, call_next):
        """Process CSRF protection for each request"""
        path = request.url.path
        method = request.method

        # Skip CSRF protection for exempt paths
        if any(path.startswith(exempt) for exempt in self.config.exempt_paths):
            self.csrf_logger.debug(f"CSRF exempt path: {path}")
            return await call_next(request)

        # Skip CSRF protection for safe methods
        if method in self.config.exempt_methods:
            # For GET requests, ensure CSRF cookie is set
            response = await call_next(request)
            if not request.cookies.get(self.config.cookie_name):
                # Set CSRF cookie for future requests
                token = self._generate_token()
                response.set_cookie(
                    self.config.cookie_name,
                    token,
                    max_age=self.config.token_lifetime_seconds,
                    httponly=False,  # Must be accessible to JavaScript
                    samesite="lax",  # Allow cookie on same-site requests
                    secure=request.url.scheme == "https",  # Secure in production
                    path="/"
                )
            return response

        # Validate CSRF for state-changing requests (POST, PUT, DELETE, PATCH)
        is_valid, error = await self._validate_csrf(request)

        if not is_valid:
            self.csrf_logger.warning(
                f"CSRF validation failed | path={path} | method={method} | reason={error}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": {
                        "code": 403,
                        "message": "CSRF validation failed",
                        "detail": error,
                        "type": "CSRFError"
                    }
                }
            )

        # CSRF validation passed, proceed with request
        self.csrf_logger.debug(f"CSRF validation passed | path={path} | method={method}")
        response = await call_next(request)

        # Ensure CSRF cookie is set in response
        if not request.cookies.get(self.config.cookie_name):
            token = self._generate_token()
            response.set_cookie(
                self.config.cookie_name,
                token,
                max_age=self.config.token_lifetime_seconds,
                httponly=False,
                samesite="lax",
                secure=request.url.scheme == "https",
                path="/"
            )

        return response

    async def _validate_csrf(self, request: Request) -> tuple[bool, str]:
        """
        Validate CSRF token and origin.

        Args:
            request: FastAPI request object

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get CSRF token from header
        csrf_token = request.headers.get(self.config.header_name)
        if not csrf_token:
            return False, f"Missing CSRF token in {self.config.header_name} header"

        # Get CSRF token from cookie
        cookie_token = request.cookies.get(self.config.cookie_name)
        if not cookie_token:
            return False, "Missing CSRF cookie"

        # Validate token matches (Double-Submit Cookie pattern)
        if not self._tokens_match(csrf_token, cookie_token):
            return False, "CSRF token mismatch"

        # Validate origin/referer headers (additional protection)
        if self.config.validate_origin:
            origin_error = self._validate_origin(request)
            if origin_error:
                return False, origin_error

        return True, ""

    def _generate_token(self) -> str:
        """
        Generate a CSRF token.

        Token format: timestamp_hmac_signature
        """
        timestamp = int(datetime.now().timestamp())
        message = f"{timestamp}"
        signature = hmac.new(
            self.config.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()[:32]

        return f"{timestamp}_{signature}"

    def _tokens_match(self, token: str, cookie_token: str) -> bool:
        """
        Validate that two CSRF tokens match and are not expired.

        Args:
            token: Token from header
            cookie_token: Token from cookie

        Returns:
            True if tokens match and are valid
        """
        if not token or not cookie_token:
            return False

        # Tokens must match exactly (Double-Submit pattern)
        if not hmac.compare_digest(token, cookie_token):
            return False

        # Check token expiration
        try:
            timestamp_str = token.split("_")[0]
            timestamp = int(timestamp_str)
            token_age = datetime.now().timestamp() - timestamp

            if token_age > self.config.token_lifetime_seconds:
                logger.info(f"CSRF token expired (age: {token_age}s)")
                return False

        except (ValueError, IndexError):
            logger.warning("Invalid CSRF token format")
            return False

        return True

    def _validate_origin(self, request: Request) -> Optional[str]:
        """
        Validate Origin and Referer headers.

        Args:
            request: FastAPI request object

        Returns:
            Error message if validation fails, None if valid
        """
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        # Get host from request
        host = request.headers.get("host", "")

        # If we have allowed_origins configured, validate against them
        if self.config.allowed_origins:
            if origin and origin not in self.config.allowed_origins:
                return f"Origin {origin} not in allowed origins"

            # Also check referer if origin not present
            if not origin and referer:
                # Extract origin from referer
                # Referer format: https://example.com/path
                referer_parts = referer.split("/")
                if len(referer_parts) >= 3:
                    referer_origin = f"{referer_parts[0]}//{referer_parts[2]}"
                    if referer_origin not in self.config.allowed_origins:
                        return f"Referer origin {referer_origin} not in allowed origins"

        # If no origin header, check referer matches host
        if not origin and referer:
            if host and host not in referer:
                return "Referer header does not match host"

        # If neither origin nor referer is present, that's suspicious
        if not origin and not referer:
            # Allow if host is localhost (development)
            if "localhost" not in host and "127.0.0.1" not in host:
                return "Missing Origin and Referer headers"

        return None


# CSRF protection decorator for specific routes
def csrf_protect(func):
    """
    Decorator to add CSRF protection to specific routes.

    Usage:
        @app.post("/install")
        @csrf_protect
        async def install_endpoint(request: Request):
            ...
    """
    from functools import wraps

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # Check if CSRF middleware has already validated
        if not hasattr(request.state, 'csrf_validated'):
            # Manual validation if middleware didn't run
            csrf_token = request.headers.get("X-CSRF-Token")
            cookie_token = request.cookies.get("csrf_token")

            if not csrf_token or not cookie_token:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF token required"
                )

            if not hmac.compare_digest(csrf_token, cookie_token):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF token mismatch"
                )

        request.state.csrf_validated = True
        return await func(request, *args, **kwargs)

    return wrapper


# Helper functions for CSRF token management
def get_csrf_token(request: Request) -> Optional[str]:
    """
    Get CSRF token from request cookies.

    Usage in templates:
        <meta name="csrf-token" content="{{ get_csrf_token(request) }}">
    """
    return request.cookies.get("csrf_token")


def get_csrf_header_name() -> str:
    """Get the header name for CSRF token"""
    return "X-CSRF-Token"


# JavaScript helper for automatically adding CSRF token to requests
CSRF_JS_HELPER = """
// CSRF Token Helper for JavaScript
// Automatically adds CSRF token to fetch/XHR requests

(function() {
    // Get CSRF token from cookie
    function getCsrfToken() {
        const name = 'csrf_token';
        const value = '; ' + document.cookie;
        const parts = value.split('; ' + name + '=');
        if (parts.length === 2) {
            return parts.pop().split(';').shift();
        }
        return null;
    }

    // Store CSRF token
    const CSRF_TOKEN = getCsrfToken();
    const CSRF_HEADER = 'X-CSRF-Token';

    // Patch fetch API
    const originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        // Add CSRF token to state-changing requests
        const method = (options.method || 'GET').toUpperCase();
        if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
            options.headers = options.headers || {};
            if (CSRF_TOKEN) {
                options.headers[CSRF_HEADER] = CSRF_TOKEN;
            }
        }
        return originalFetch.call(this, url, options);
    };

    // Patch XMLHttpRequest
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function(method, url, ...args) {
        this._method = method.toUpperCase();
        this._url = url;
        return originalOpen.apply(this, [method, url, ...args]);
    };

    XMLHttpRequest.prototype.send = function(data) {
        if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(this._method)) {
            if (CSRF_TOKEN) {
                this.setRequestHeader(CSRF_HEADER, CSRF_TOKEN);
            }
        }
        return originalSend.call(this, data);
    };

    console.log('CSRF protection enabled');
})();
"""


# Create CSRF middleware instance
def create_csrf_middleware(config: CSRFConfig = None) -> CSRFMiddleware:
    """
    Create CSRF middleware instance.

    Usage:
        from playstorE.core.security.csrf import create_csrf_middleware, CSRFConfig

        config = CSRFConfig(
            secret_key=os.getenv("SECRET_KEY"),
            allowed_origins=["http://localhost:3000"]
        )
        app.add_middleware(create_csrf_middleware(config))
    """
    return CSRFMiddleware(app=None, config=config)
