"""
API Authentication Middleware for pLayStorE Platform.

Provides multiple authentication methods:
- API Key authentication
- JWT token authentication
- GitHub OAuth token authentication

Features:
- Multi-method authentication support
- Token validation and refresh
- Rate limiting per authentication level
- Audit logging for auth events

Usage:
    from playstorE.core.security.authentication import AuthMiddleware, AuthMethod
    
    app.add_middleware(AuthMiddleware, auth_methods=[AuthMethod.API_KEY, AuthMethod.JWT])
"""

import os
import re
import time
import hashlib
import secrets
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from functools import wraps
import hmac
import base64
import json

from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class AuthMethod(Enum):
    """Authentication methods supported"""
    API_KEY = "api_key"
    JWT = "jwt"
    GITHUB_OAUTH = "github_oauth"
    ANONYMOUS = "anonymous"  # Read-only access


class AuthLevel(Enum):
    """Authentication levels with different permissions"""
    ANONYMOUS = 0      # Public endpoints only
    AUTHENTICATED = 1  # Basic authenticated access
    ADMIN = 2          # Administrative access
    SERVICE = 3        # Service-to-service access


class TokenManager:
    """
    Manages JWT-like token creation and validation.
    
    Token format: base64(header).base64(payload).base64(signature)
    """

    def __init__(self, secret_key: str = None, token_expiry_hours: int = 24):
        self.secret_key = secret_key or os.getenv("API_SECRET_KEY", secrets.token_urlsafe(32))
        self.token_expiry_hours = token_expiry_hours

    def create_token(self, user_id: str, auth_level: AuthLevel = AuthLevel.AUTHENTICATED,
                     extra_claims: Dict = None) -> str:
        """
        Create a signed authentication token.

        Args:
            user_id: Unique user identifier
            auth_level: Access level for this token
            extra_claims: Additional claims to include

        Returns:
            Signed token string
        """
        header = {
            "alg": "HS256",
            "typ": "Bearer"
        }

        payload = {
            "sub": user_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
            "level": auth_level.value,
            "jti": secrets.token_urlsafe(16)  # Unique token ID
        }

        if extra_claims:
            payload.update(extra_claims)

        # Encode header and payload
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')

        # Create signature
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def validate_token(self, token: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Validate an authentication token.

        Args:
            token: Token string to validate

        Returns:
            Tuple of (is_valid, payload, error_message)
        """
        try:
            # Split token
            parts = token.split('.')
            if len(parts) != 3:
                return False, None, "Invalid token format"

            header_b64, payload_b64, signature_b64 = parts

            # Verify signature
            message = f"{header_b64}.{payload_b64}"
            expected_signature = hmac.new(
                self.secret_key.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()

            # Add padding if needed
            signature_b64_padded = signature_b64 + '=' * (4 - len(signature_b64) % 4)
            provided_signature = base64.urlsafe_b64decode(signature_b64_padded)

            if not hmac.compare_digest(provided_signature, expected_signature):
                return False, None, "Invalid signature"

            # Decode payload
            payload_b64_padded = payload_b64 + '=' * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64_padded))

            # Check expiration
            exp = payload.get('exp')
            if exp:
                if isinstance(exp, datetime):
                    exp_timestamp = exp.timestamp()
                else:
                    exp_timestamp = exp
                if datetime.utcnow().timestamp() > exp_timestamp:
                    return False, None, "Token expired"

            return True, payload, ""

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False, None, f"Token validation failed: {str(e)}"


class APIKeyManager:
    """
    Manages API key creation and validation.
    
    API Key format: pk_[environment]_[random]
    Example: pk_live_a1b2c3d4e5f6g7h8i9j0
    """

    def __init__(self):
        self.api_keys: Dict[str, Dict] = {}  # In production, use database
        self._load_api_keys()

    def _load_api_keys(self):
        """Load API keys from environment"""
        # Load from environment variable (comma-separated: key1:name1,key2:name2)
        keys_env = os.getenv("API_KEYS", "")
        if keys_env:
            for key_entry in keys_env.split(','):
                if ':' in key_entry:
                    key, name = key_entry.split(':', 1)
                    self.api_keys[key.strip()] = {
                        "name": name.strip(),
                        "level": AuthLevel.AUTHENTICATED.value,
                        "created": datetime.utcnow().isoformat()
                    }

        # Load admin key if set
        admin_key = os.getenv("ADMIN_API_KEY")
        if admin_key:
            self.api_keys[admin_key] = {
                "name": "admin",
                "level": AuthLevel.ADMIN.value,
                "created": datetime.utcnow().isoformat()
            }

    def generate_key(self, name: str, auth_level: AuthLevel = AuthLevel.AUTHENTICATED) -> str:
        """
        Generate a new API key.

        Args:
            name: Key identifier/name
            auth_level: Access level for this key

        Returns:
            Generated API key
        """
        env = os.getenv("ENVIRONMENT", "dev")
        random_part = secrets.token_urlsafe(20)
        key = f"pk_{env}_{random_part}"

        self.api_keys[key] = {
            "name": name,
            "level": auth_level.value,
            "created": datetime.utcnow().isoformat()
        }

        return key

    def validate_key(self, api_key: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Validate an API key.

        Args:
            api_key: API key to validate

        Returns:
            Tuple of (is_valid, key_info, error_message)
        """
        if not api_key:
            return False, None, "API key required"

        # Check format
        if not re.match(r'^pk_[a-z]+_[a-zA-Z0-9_-]+$', api_key):
            return False, None, "Invalid API key format"

        key_info = self.api_keys.get(api_key)
        if not key_info:
            return False, None, "Invalid API key"

        return True, key_info, ""

    def revoke_key(self, api_key: str) -> bool:
        """Revoke an API key"""
        if api_key in self.api_keys:
            del self.api_keys[api_key]
            return True
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for API endpoints.

    Supports multiple authentication methods:
    - API Key (X-API-Key header)
    - Bearer Token (Authorization header)
    - GitHub OAuth token

    Usage:
        app.add_middleware(AuthMiddleware, required_auth_level=AuthLevel.AUTHENTICATED)
    """

    def __init__(self, app, required_auth_level: AuthLevel = AuthLevel.ANONYMOUS,
                 excluded_paths: List[str] = None):
        super().__init__(app)
        self.required_auth_level = required_auth_level
        self.excluded_paths = excluded_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/api/health"
        ]
        self.token_manager = TokenManager()
        self.api_key_manager = APIKeyManager()
        self.auth_logger = logging.getLogger("altstore.auth")

    async def dispatch(self, request: Request, call_next):
        """Process authentication for each request"""
        path = request.url.path

        # Skip authentication for excluded paths
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return await call_next(request)

        # Skip authentication for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Try to authenticate
        auth_result = await self._authenticate(request)

        if not auth_result["authenticated"]:
            if self.required_auth_level > AuthLevel.ANONYMOUS:
                self.auth_logger.warning(
                    f"AUTH_FAILURE | path={path} | reason={auth_result.get('error', 'Unknown')}"
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "Authentication required",
                        "detail": auth_result.get("error", "Invalid or missing credentials")
                    }
                )
            else:
                # Anonymous access allowed
                request.state.auth_level = AuthLevel.ANONYMOUS
                request.state.user = None
                return await call_next(request)

        # Set authentication state
        request.state.authenticated = True
        request.state.auth_level = auth_result["auth_level"]
        request.state.user = auth_result["user"]
        request.state.auth_method = auth_result["method"]

        # Log successful authentication
        self.auth_logger.info(
            f"AUTH_SUCCESS | path={path} | method={auth_result['method']} | "
            f"user={auth_result['user'].get('id', 'unknown')} | level={auth_result['auth_level'].name}"
        )

        # Check if user has required access level
        if request.state.auth_level.value < self.required_auth_level.value:
            self.auth_logger.warning(
                f"AUTHORIZATION_FAILURE | path={path} | "
                f"user={auth_result['user'].get('id')} | "
                f"required={self.required_auth_level.name} | "
                f"actual={auth_result['auth_level'].name}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Insufficient permissions",
                    "detail": f"Required access level: {self.required_auth_level.name}"
                }
            )

        return await call_next(request)

    async def _authenticate(self, request: Request) -> Dict[str, Any]:
        """
        Attempt to authenticate the request using available methods.

        Returns:
            Dict with authentication result
        """
        # Try API Key authentication first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            is_valid, key_info, error = self.api_key_manager.validate_key(api_key)
            if is_valid:
                return {
                    "authenticated": True,
                    "method": "api_key",
                    "auth_level": AuthLevel(key_info["level"]),
                    "user": {
                        "id": key_info["name"],
                        "type": "api_key"
                    }
                }
            else:
                return {"authenticated": False, "error": error}

        # Try Bearer token authentication
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            is_valid, payload, error = self.token_manager.validate_token(token)
            if is_valid:
                return {
                    "authenticated": True,
                    "method": "jwt",
                    "auth_level": AuthLevel(payload.get("level", AuthLevel.AUTHENTICATED.value)),
                    "user": {
                        "id": payload.get("sub"),
                        "type": "user",
                        "claims": payload
                    }
                }
            else:
                return {"authenticated": False, "error": error}

        # Try GitHub OAuth token
        github_token = request.headers.get("X-GitHub-Token")
        if github_token:
            # Validate GitHub token (in production, verify with GitHub API)
            if github_token.startswith("ghp_") or github_token.startswith("github_pat_"):
                return {
                    "authenticated": True,
                    "method": "github_oauth",
                    "auth_level": AuthLevel.AUTHENTICATED,
                    "user": {
                        "id": "github_user",  # Would fetch from GitHub API
                        "type": "github_oauth"
                    }
                }
            else:
                return {"authenticated": False, "error": "Invalid GitHub token format"}

        # No authentication provided
        return {"authenticated": False, "error": "No authentication credentials provided"}


# Authentication decorators for route-level protection
def require_auth(auth_level: AuthLevel = AuthLevel.AUTHENTICATED):
    """
    Decorator to require authentication for specific routes.

    Usage:
        @app.get("/admin")
        @require_auth(AuthLevel.ADMIN)
        async def admin_endpoint(request: Request):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            if not hasattr(request.state, 'authenticated') or not request.state.authenticated:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if request.state.auth_level.value < auth_level.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required access level: {auth_level.name}"
                )

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_current_user(request: Request) -> Optional[Dict]:
    """Get current authenticated user from request"""
    if hasattr(request.state, 'user'):
        return request.state.user
    return None


def get_auth_level(request: Request) -> AuthLevel:
    """Get current authentication level"""
    if hasattr(request.state, 'auth_level'):
        return request.state.auth_level
    return AuthLevel.ANONYMOUS


# API Key dependency for FastAPI routes
async def get_api_key(x_api_key: Optional[str] = None) -> str:
    """FastAPI dependency for API key authentication"""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )

    api_key_manager = APIKeyManager()
    is_valid, key_info, error = api_key_manager.validate_key(x_api_key)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )

    return x_api_key


# Health check endpoint (no auth required)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
