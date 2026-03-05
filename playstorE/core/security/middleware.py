"""
Security Middleware for pLayStorE API.

Provides security headers and protections:
- Content-Security-Policy (CSP)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Strict-Transport-Security
- Referrer-Policy
- Permissions-Policy

Based on OWASP security header recommendations.
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, List, Optional
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Implements OWASP recommended security headers to protect against:
    - XSS attacks (via CSP)
    - Clickjacking (via X-Frame-Options)
    - MIME type sniffing (via X-Content-Type-Options)
    - Protocol downgrade attacks (via HSTS)
    - Information leakage (via Referrer-Policy)
    """

    def __init__(
        self,
        app,
        # CSP Configuration
        csp_default_src: List[str] = None,
        csp_script_src: List[str] = None,
        csp_style_src: List[str] = None,
        csp_img_src: List[str] = None,
        csp_font_src: List[str] = None,
        csp_connect_src: List[str] = None,
        csp_frame_ancestors: List[str] = None,
        # HSTS Configuration
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = True,
        # Other Configuration
        report_uri: Optional[str] = None,
    ):
        super().__init__(app)

        # Default CSP directives (secure by default)
        self.csp_default_src = csp_default_src or ["'self'"]
        self.csp_script_src = csp_script_src or ["'self'"]  # No inline scripts
        self.csp_style_src = csp_style_src or ["'self'"]  # No inline styles
        self.csp_img_src = csp_img_src or ["'self'", "data:", "https:"]
        self.csp_font_src = csp_font_src or ["'self'"]
        self.csp_connect_src = csp_connect_src or ["'self'"]
        self.csp_frame_ancestors = csp_frame_ancestors or ["'none'"]  # Prevent clickjacking
        self.report_uri = report_uri

        # HSTS configuration
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload

    def _build_csp_header(self) -> str:
        """Build Content-Security-Policy header value"""
        directives = []

        directives.append(f"default-src {' '.join(self.csp_default_src)}")
        directives.append(f"script-src {' '.join(self.csp_script_src)}")
        directives.append(f"style-src {' '.join(self.csp_style_src)}")
        directives.append(f"img-src {' '.join(self.csp_img_src)}")
        directives.append(f"font-src {' '.join(self.csp_font_src)}")
        directives.append(f"connect-src {' '.join(self.csp_connect_src)}")
        directives.append(f"frame-ancestors {' '.join(self.csp_frame_ancestors)}")

        # Add report-uri if configured
        if self.report_uri:
            directives.append(f"report-uri {self.report_uri}")
            directives.append(f"report-to csp-endpoint")

        return "; ".join(directives)

    def _build_hsts_header(self) -> str:
        """Build Strict-Transport-Security header value"""
        header = f"max-age={self.hsts_max_age}"

        if self.hsts_include_subdomains:
            header += "; includeSubDomains"

        if self.hsts_preload:
            header += "; preload"

        return header

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response"""
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Error in security middleware: {e}")
            raise

        # Content-Security-Policy
        response.headers["Content-Security-Policy"] = self._build_csp_header()

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS Protection (legacy, but still useful for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy - limit information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy - disable unnecessary features
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "ambient-light-sensor=(), "
            "autoplay=(), "
            "battery=(), "
            "camera=(), "
            "cross-origin-isolated=(), "
            "display-capture=(), "
            "document-domain=(), "
            "encrypted-media=(), "
            "execution-while-not-rendered=(), "
            "execution-while-out-of-viewport=(), "
            "fullscreen=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "keyboard-map=(), "
            "magnetometer=(), "
            "microphone=(), "
            "midi=(), "
            "navigation-override=(), "
            "payment=(), "
            "picture-in-picture=(), "
            "publickey-credentials-get=(), "
            "screen-wake-lock=(), "
            "sync-xhr=(), "
            "usb=(), "
            "web-share=(), "
            "xr-spatial-tracking=()"
        )

        # Only add HSTS on HTTPS (in production, this should always be HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = self._build_hsts_header()

        # Remove potentially dangerous headers
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Audit logging middleware for security-relevant events.

    Logs:
    - All authentication attempts
    - Authorization failures
    - Rate limit violations
    - Input validation failures
    - Suspicious request patterns
    """

    def __init__(self, app, log_level: str = "INFO"):
        super().__init__(app)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.audit_logger = logging.getLogger("altstore.audit")

        # Ensure audit logger has a handler
        if not self.audit_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.audit_logger.addHandler(handler)
            self.audit_logger.setLevel(self.log_level)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log security-relevant request information"""
        # Extract client information
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        method = request.method
        path = request.url.path
        query_params = str(request.url.query) if request.url.query else ""

        # Log request start
        self.audit_logger.log(
            self.log_level,
            f"AUDIT: REQUEST_START | "
            f"ip={client_ip} | "
            f"method={method} | "
            f"path={path} | "
            f"query={query_params} | "
            f"user_agent={user_agent}"
        )

        try:
            response = await call_next(request)

            # Log response
            self.audit_logger.log(
                self.log_level,
                f"AUDIT: REQUEST_END | "
                f"ip={client_ip} | "
                f"method={method} | "
                f"path={path} | "
                f"status={response.status_code}"
            )

            # Log potential security issues
            if response.status_code == 401:
                self.audit_logger.warning(
                    f"AUDIT: AUTH_FAILURE | "
                    f"ip={client_ip} | "
                    f"method={method} | "
                    f"path={path}"
                )
            elif response.status_code == 403:
                self.audit_logger.warning(
                    f"AUDIT: AUTHORIZATION_FAILURE | "
                    f"ip={client_ip} | "
                    f"method={method} | "
                    f"path={path}"
                )
            elif response.status_code == 429:
                self.audit_logger.warning(
                    f"AUDIT: RATE_LIMIT_EXCEEDED | "
                    f"ip={client_ip} | "
                    f"method={method} | "
                    f"path={path}"
                )
            elif response.status_code >= 500:
                self.audit_logger.error(
                    f"AUDIT: SERVER_ERROR | "
                    f"ip={client_ip} | "
                    f"method={method} | "
                    f"path={path} | "
                    f"status={response.status_code}"
                )

            return response

        except Exception as e:
            # Log exception
            self.audit_logger.error(
                f"AUDIT: EXCEPTION | "
                f"ip={client_ip} | "
                f"method={method} | "
                f"path={path} | "
                f"error={type(e).__name__}: {str(e)}"
            )
            raise


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for early input validation and sanitization.

    Validates:
    - Request path for path traversal attempts
    - Query parameters for injection attacks
    - Request headers for suspicious patterns
    """

    def __init__(self, app):
        super().__init__(app)
        import re
        self.path_traversal_pattern = re.compile(r'\.\.[\\/]|%2e%2e[\\/]', re.IGNORECASE)
        self.sql_injection_pattern = re.compile(
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
            re.IGNORECASE
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate request before processing"""
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        # Check for path traversal in URL
        if self.path_traversal_pattern.search(path):
            logger.warning(
                f"SECURITY: Path traversal attempt detected | "
                f"ip={client_ip} | method={method} | path={path}"
            )
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid request path"}
            )

        # Check for SQL injection in query params
        query = request.url.query
        if query and self.sql_injection_pattern.search(query):
            logger.warning(
                f"SECURITY: SQL injection attempt detected | "
                f"ip={client_ip} | method={method} | query={query}"
            )
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid query parameters"}
            )

        # Check for suspicious user agents
        user_agent = request.headers.get("user-agent", "")
        suspicious_agents = ["sqlmap", "nikto", "nmap", "masscan", "zgrab"]
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            logger.warning(
                f"SECURITY: Suspicious user agent | "
                f"ip={client_ip} | method={method} | user_agent={user_agent}"
            )
            # Don't block, just log for monitoring

        return await call_next(request)


def setup_security_middleware(app, config: dict = None):
    """
    Configure and add all security middleware to FastAPI app.

    Args:
        app: FastAPI application
        config: Optional configuration dictionary
    """
    config = config or {}

    # Add input validation middleware first (runs before other middleware)
    app.add_middleware(InputValidationMiddleware)

    # Add audit logging middleware
    app.add_middleware(
        AuditLoggingMiddleware,
        log_level=config.get("audit_log_level", "INFO")
    )

    # Add security headers middleware last (wraps all other middleware)
    app.add_middleware(
        SecurityHeadersMiddleware,
        csp_default_src=config.get("csp_default_src", ["'self'"]),
        csp_script_src=config.get("csp_script_src", ["'self'"]),
        csp_style_src=config.get("csp_style_src", ["'self'"]),
        csp_img_src=config.get("csp_img_src", ["'self'", "data:", "https:"]),
        csp_font_src=config.get("csp_font_src", ["'self'"]),
        csp_connect_src=config.get("csp_connect_src", ["'self'"]),
        csp_frame_ancestors=config.get("csp_frame_ancestors", ["'none'"]),
        hsts_max_age=config.get("hsts_max_age", 31536000),
        hsts_include_subdomains=config.get("hsts_include_subdomains", True),
        hsts_preload=config.get("hsts_preload", True),
        report_uri=config.get("csp_report_uri"),
    )

    logger.info("Security middleware configured successfully")
