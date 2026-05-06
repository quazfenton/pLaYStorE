"""
Input Validation Utilities for pLayStorE Platform.

Provides:
- Repository name validation
- Path validation
- Manifest validation helpers
- User input sanitization
- Rate limit validation

Usage:
    from playstorE.core.validation import validate_github_repo, validate_path
    
    # Validate GitHub repository name
    validate_github_repo("owner/repo")  # Raises if invalid
    
    # Validate path
    validate_path(user_path, base_dir)  # Ensures path is within base_dir
"""

import re
import os
import logging
from typing import Optional, Tuple, List, Any, Union
from pathlib import Path
from datetime import datetime

from playstorE.core.errors import ValidationError, SecurityError, PathTraversalError

logger = logging.getLogger(__name__)


# Validation patterns
GITHUB_REPO_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_\.]+/[a-zA-Z0-9][a-zA-Z0-9\-_\.]+$')
GITHUB_USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_]+$')
SEMVER_PATTERN = re.compile(r'^v?\d+\.\d+\.\d+(-[a-zA-Z0-9\.]+)?(\+[a-zA-Z0-9\.]+)?$')
APP_ID_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9\-_\.]*$')


def validate_github_repo(repo: str, field_name: str = "github_repo") -> str:
    """
    Validate GitHub repository name format.

    Args:
        repo: Repository name in format "owner/name"
        field_name: Name of field for error messages

    Returns:
        Validated repository name

    Raises:
        ValidationError: If repository format is invalid
    """
    if not repo or not isinstance(repo, str):
        raise ValidationError(f"{field_name} must be a non-empty string")

    repo = repo.strip()

    # Check length
    if len(repo) > 100:
        raise ValidationError(f"{field_name} must be 100 characters or less")

    # Check format
    if not GITHUB_REPO_PATTERN.match(repo):
        raise ValidationError(
            f"{field_name} must be in format 'owner/name'. "
            f"Example: 'torvalds/linux'",
            {"received": repo, "format": "owner/name"}
        )

    # Check for suspicious patterns
    suspicious_patterns = ['..', '//', '\\\\', '://', '@']
    for pattern in suspicious_patterns:
        if pattern in repo:
            raise SecurityError(
                f"{field_name} contains suspicious pattern",
                {"pattern": pattern, "value": repo}
            )

    return repo


def validate_github_username(username: str, field_name: str = "username") -> str:
    """
    Validate GitHub username format.

    Args:
        username: GitHub username
        field_name: Name of field for error messages

    Returns:
        Validated username

    Raises:
        ValidationError: If username format is invalid
    """
    if not username or not isinstance(username, str):
        raise ValidationError(f"{field_name} must be a non-empty string")

    username = username.strip()

    # Check length
    if len(username) > 39:  # GitHub username limit
        raise ValidationError(f"{field_name} must be 39 characters or less")

    # Check format
    if not GITHUB_USERNAME_PATTERN.match(username):
        raise ValidationError(
            f"{field_name} contains invalid characters",
            {"received": username}
        )

    return username


def validate_path(
    user_path: str,
    base_dir: Union[str, Path],
    field_name: str = "path",
    must_exist: bool = False
) -> Path:
    """
    Validate that a user-provided path is within an allowed base directory.

    Prevents path traversal attacks by ensuring the resolved path
    is within the base directory.

    Args:
        user_path: User-provided path
        base_dir: Base directory that path must be within
        field_name: Name of field for error messages
        must_exist: Whether the path must already exist

    Returns:
        Validated Path object

    Raises:
        PathTraversalError: If path escapes base directory
        ValidationError: If path doesn't exist when required
    """
    if not user_path or not isinstance(user_path, str):
        raise ValidationError(f"{field_name} must be a non-empty string")

    # Convert to Path objects
    user_path_obj = Path(user_path)
    base_dir_obj = Path(base_dir).resolve()

    # Check for obvious traversal attempts
    if '..' in str(user_path):
        raise PathTraversalError(
            f"{field_name} contains directory traversal sequence",
            {"path": user_path}
        )

    # Check for absolute paths
    if user_path_obj.is_absolute():
        # Resolve and check if within allowed directories
        resolved = user_path_obj.resolve()
    else:
        # For relative paths, resolve against current working directory
        resolved = (Path.cwd() / user_path_obj).resolve()

    # Ensure resolved path is within base directory or home
    home_dir = Path.home().resolve()
    is_within_base = str(resolved).startswith(str(base_dir_obj))
    is_within_home = str(resolved).startswith(str(home_dir))

    if not (is_within_base or is_within_home):
        raise PathTraversalError(
            f"{field_name} must be within base directory or user home",
            {
                "path": str(resolved),
                "base_dir": str(base_dir_obj),
                "home_dir": str(home_dir)
            }
        )

    # Check existence if required
    if must_exist and not resolved.exists():
        raise ValidationError(
            f"{field_name} does not exist",
            {"path": str(resolved)}
        )

    return resolved


def validate_semver(version: str, field_name: str = "version") -> str:
    """
    Validate semantic version format.

    Args:
        version: Version string
        field_name: Name of field for error messages

    Returns:
        Validated version string

    Raises:
        ValidationError: If version format is invalid
    """
    if not version or not isinstance(version, str):
        raise ValidationError(f"{field_name} must be a non-empty string")

    version = version.strip()

    # Check length
    if len(version) > 50:
        raise ValidationError(f"{field_name} must be 50 characters or less")

    # Check format
    if not SEMVER_PATTERN.match(version):
        raise ValidationError(
            f"{field_name} must be in semantic version format",
            {"received": version, "format": "X.Y.Z"}
        )

    return version


def validate_app_id(app_id: str, field_name: str = "app_id") -> str:
    """
    Validate application ID format.

    Args:
        app_id: Application identifier
        field_name: Name of field for error messages

    Returns:
        Validated app ID

    Raises:
        ValidationError: If app ID format is invalid
    """
    if not app_id or not isinstance(app_id, str):
        raise ValidationError(f"{field_name} must be a non-empty string")

    app_id = app_id.strip()

    # Check length
    if len(app_id) > 100:
        raise ValidationError(f"{field_name} must be 100 characters or less")

    # Check format
    if not APP_ID_PATTERN.match(app_id):
        raise ValidationError(
            f"{field_name} must start with a letter and contain only alphanumeric characters, hyphens, underscores, or dots",
            {"received": app_id}
        )

    return app_id


def validate_search_query(query: str, max_length: int = 256, field_name: str = "query") -> str:
    """
    Validate and sanitize search query.

    Args:
        query: Search query string
        max_length: Maximum allowed length
        field_name: Name of field for error messages

    Returns:
        Sanitized query string

    Raises:
        ValidationError: If query is invalid
    """
    if not query or not isinstance(query, str):
        raise ValidationError(f"{field_name} must be a non-empty string")

    query = query.strip()

    # Check length
    if len(query) > max_length:
        raise ValidationError(f"{field_name} must be {max_length} characters or less")

    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '\\', ';', '`', '$', '|', '&']
    sanitized = query
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')

    # Check for SQL injection patterns
    sql_patterns = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION']
    for pattern in sql_patterns:
        if pattern in sanitized.upper():
            logger.warning(f"Potential SQL injection in {field_name}: {query}")
            raise ValidationError(
                f"{field_name} contains invalid pattern",
                {"pattern": pattern}
            )

    return sanitized


def validate_port(port: Any, field_name: str = "port") -> int:
    """
    Validate port number.

    Args:
        port: Port number
        field_name: Name of field for error messages

    Returns:
        Validated port number

    Raises:
        ValidationError: If port is invalid
    """
    try:
        port_int = int(port)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be an integer")

    if port_int < 1 or port_int > 65535:
        raise ValidationError(f"{field_name} must be between 1 and 65535")

    return port_int


def validate_timeout(timeout: Any, field_name: str = "timeout", max_timeout: int = 3600) -> int:
    """
    Validate timeout value.

    Args:
        timeout: Timeout in seconds
        field_name: Name of field for error messages
        max_timeout: Maximum allowed timeout

    Returns:
        Validated timeout

    Raises:
        ValidationError: If timeout is invalid
    """
    try:
        timeout_int = int(timeout)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be an integer")

    if timeout_int < 0:
        raise ValidationError(f"{field_name} must be non-negative")

    if timeout_int > max_timeout:
        raise ValidationError(f"{field_name} must be {max_timeout} seconds or less")

    return timeout_int


def validate_file_size(size: Any, field_name: str = "file_size", max_size_mb: int = 100) -> int:
    """
    Validate file size.

    Args:
        size: File size in bytes
        field_name: Name of field for error messages
        max_size_mb: Maximum allowed size in MB

    Returns:
        Validated file size

    Raises:
        ValidationError: If file size is invalid
    """
    try:
        size_int = int(size)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be an integer")

    if size_int < 0:
        raise ValidationError(f"{field_name} must be non-negative")

    max_size_bytes = max_size_mb * 1024 * 1024
    if size_int > max_size_bytes:
        raise ValidationError(f"{field_name} must be {max_size_mb}MB or less")

    return size_int


def validate_mime_type(mime_type: str, allowed_types: List[str] = None, field_name: str = "content_type") -> str:
    """
    Validate MIME type.

    Args:
        mime_type: MIME type string
        allowed_types: List of allowed MIME types
        field_name: Name of field for error messages

    Returns:
        Validated MIME type

    Raises:
        ValidationError: If MIME type is invalid
    """
    if not mime_type or not isinstance(mime_type, str):
        raise ValidationError(f"{field_name} must be a non-empty string")

    mime_type = mime_type.strip().lower()

    # Basic MIME type format check
    if '/' not in mime_type:
        raise ValidationError(f"{field_name} must be in format 'type/subtype'")

    # Check against allowed types if provided
    if allowed_types and mime_type not in allowed_types:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(allowed_types)}",
            {"received": mime_type}
        )

    return mime_type


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename for safe storage.

    Args:
        filename: Original filename
        max_length: Maximum filename length

    Returns:
        Sanitized filename
    """
    if not filename or not isinstance(filename, str):
        raise ValidationError("Filename must be a non-empty string")

    # Remove path components
    filename = os.path.basename(filename)

    # Remove or replace dangerous characters
    dangerous_chars = {
        '<': '_', '>': '_', ':': '_', '"': '_',
        '/': '_', '\\': '_', '|': '_', '?': '_', '*': '_'
    }

    sanitized = filename
    for char, replacement in dangerous_chars.items():
        sanitized = sanitized.replace(char, replacement)

    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')

    # Trim length
    if len(sanitized) > max_length:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:max_length - len(ext)] + ext

    # Ensure not empty or reserved
    if not sanitized or sanitized in ['.', '..', 'CON', 'PRN', 'AUX', 'NUL']:
        sanitized = 'unnamed_file'

    return sanitized


def validate_url(url: str, allowed_schemes: List[str] = None, field_name: str = "url") -> str:
    """
    Validate URL format and scheme.

    Args:
        url: URL string
        allowed_schemes: List of allowed URL schemes
        field_name: Name of field for error messages

    Returns:
        Validated URL

    Raises:
        ValidationError: If URL is invalid
        SecurityError: If URL scheme is dangerous
    """
    if not url or not isinstance(url, str):
        raise ValidationError(f"{field_name} must be a non-empty string")

    url = url.strip()

    # Check length
    if len(url) > 2048:
        raise ValidationError(f"{field_name} must be 2048 characters or less")

    # Check for dangerous schemes
    dangerous_schemes = ['javascript:', 'data:', 'vbscript:', 'file:']
    url_lower = url.lower()
    for scheme in dangerous_schemes:
        if url_lower.startswith(scheme):
            raise SecurityError(
                f"{field_name} uses dangerous scheme",
                {"scheme": scheme, "url": url}
            )

    # Check for allowed schemes if provided
    if allowed_schemes:
        has_allowed_scheme = False
        for scheme in allowed_schemes:
            if url_lower.startswith(f"{scheme}:"):
                has_allowed_scheme = True
                break

        if not has_allowed_scheme:
            raise ValidationError(
                f"{field_name} must use one of these schemes: {', '.join(allowed_schemes)}",
                {"url": url}
            )

    # Basic URL format check
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(url):
        raise ValidationError(
            f"{field_name} is not a valid URL",
            {"url": url}
        )

    return url


def validate_email(email: str, field_name: str = "email") -> str:
    """
    Validate email format.

    Args:
        email: Email address
        field_name: Name of field for error messages

    Returns:
        Validated email

    Raises:
        ValidationError: If email format is invalid
    """
    if not email or not isinstance(email, str):
        raise ValidationError(f"{field_name} must be a non-empty string")

    email = email.strip()

    # Check length
    if len(email) > 254:
        raise ValidationError(f"{field_name} must be 254 characters or less")

    # Basic email format check
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not email_pattern.match(email):
        raise ValidationError(
            f"{field_name} is not a valid email address",
            {"email": email}
        )

    return email


def validate_json_size(data: Any, max_size_kb: int = 1024, field_name: str = "data") -> Any:
    """
    Validate JSON data size.

    Args:
        data: JSON data (dict, list, etc.)
        max_size_kb: Maximum size in KB
        field_name: Name of field for error messages

    Returns:
        The same data if valid

    Raises:
        ValidationError: If data is too large
    """
    import json

    try:
        json_str = json.dumps(data)
        size_kb = len(json_str.encode('utf-8')) / 1024

        if size_kb > max_size_kb:
            raise ValidationError(
                f"{field_name} is too large ({size_kb:.1f}KB, max {max_size_kb}KB)",
                {"size_kb": size_kb, "max_kb": max_size_kb}
            )

        return data

    except TypeError as e:
        raise ValidationError(f"{field_name} must be JSON-serializable: {str(e)}")
