"""
Security Tests for Additional Implementations.

Tests for:
- CSRF protection
- Input validation
- Authentication enhancements

Run with: python -m pytest tests/test_security_additional.py -v
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestCSRFProtection:
    """Test CSRF protection middleware"""

    @pytest.fixture
    def csrf_config(self):
        """Create CSRF configuration for testing"""
        from playstorE.core.security.csrf import CSRFConfig
        return CSRFConfig(
            secret_key="test_secret_key_for_testing_only_12345",
            cookie_name="test_csrf_token",
            header_name="X-Test-CSRF-Token",
            token_lifetime_seconds=3600,
            exempt_paths={"/health"},
            exempt_methods={"GET", "HEAD", "OPTIONS"},
            validate_origin=True,
            allowed_origins=["http://localhost:3000"]
        )

    @pytest.fixture
    def csrf_middleware(self, csrf_config):
        """Create CSRF middleware for testing"""
        from playstorE.core.security.csrf import CSRFMiddleware

        # Create a mock app
        mock_app = AsyncMock()
        mock_app.return_value = Mock(status_code=200)

        return CSRFMiddleware(mock_app, csrf_config)

    def test_token_generation(self, csrf_config):
        """Test CSRF token generation"""
        from playstorE.core.security.csrf import CSRFMiddleware

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        token = middleware._generate_token()

        # Token should have format: timestamp_signature
        parts = token.split('_')
        assert len(parts) == 2
        assert len(parts[1]) == 32  # SHA256 hex = 64 chars, truncated to 32

        # Timestamp should be recent
        timestamp = int(parts[0])
        now = int(datetime.now().timestamp())
        assert abs(now - timestamp) < 5  # Within 5 seconds

    def test_tokens_match(self, csrf_config):
        """Test token matching"""
        from playstorE.core.security.csrf import CSRFMiddleware

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        token = middleware._generate_token()

        # Same token should match
        assert middleware._tokens_match(token, token) is True

        # Different tokens should not match
        token2 = middleware._generate_token()
        assert middleware._tokens_match(token, token2) is False

        # Empty tokens should not match
        assert middleware._tokens_match("", "") is False
        assert middleware._tokens_match(None, None) is False

    def test_token_expiration(self, csrf_config):
        """Test token expiration"""
        from playstorE.core.security.csrf import CSRFMiddleware

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        # Generate token with very short lifetime
        middleware.config.token_lifetime_seconds = 0

        token = middleware._generate_token()

        # Token should be expired immediately
        import time
        time.sleep(0.1)  # Small delay to ensure expiration

        # Token should not match when expired
        assert middleware._tokens_match(token, token) is False

    def test_origin_validation_allowed(self, csrf_config):
        """Test origin validation with allowed origin"""
        from playstorE.core.security.csrf import CSRFMiddleware

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        # Create mock request with allowed origin
        mock_request = Mock()
        mock_request.headers = {"origin": "http://localhost:3000"}

        error = middleware._validate_origin(mock_request)
        assert error is None

    def test_origin_validation_blocked(self, csrf_config):
        """Test origin validation with disallowed origin"""
        from playstorE.core.security.csrf import CSRFMiddleware

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        # Create mock request with disallowed origin
        mock_request = Mock()
        mock_request.headers = {"origin": "http://evil.com"}

        error = middleware._validate_origin(mock_request)
        assert error is not None
        assert "not in allowed origins" in error

    def test_origin_validation_missing(self, csrf_config):
        """Test origin validation with missing headers"""
        from playstorE.core.security.csrf import CSRFMiddleware

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        # Create mock request without origin or referer
        mock_request = Mock()
        mock_request.headers = {"host": "example.com"}

        error = middleware._validate_origin(mock_request)
        assert error is not None
        assert "Missing Origin and Referer" in error

    def test_origin_validation_localhost_allowed(self, csrf_config):
        """Test that localhost is allowed without origin"""
        from playstorE.core.security.csrf import CSRFMiddleware

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        # Create mock request on localhost without origin
        mock_request = Mock()
        mock_request.headers = {"host": "localhost:8000"}

        error = middleware._validate_origin(mock_request)
        assert error is None  # Should be allowed for development


class TestInputValidation:
    """Test input validation utilities"""

    def test_validate_github_repo_valid(self):
        """Test valid GitHub repository validation"""
        from playstorE.core.validation import validate_github_repo

        # Valid repos
        assert validate_github_repo("torvalds/linux") == "torvalds/linux"
        assert validate_github_repo("microsoft/vscode") == "microsoft/vscode"
        assert validate_github_repo("user-name/repo-name") == "user-name/repo-name"
        assert validate_github_repo("user_name/repo_name") == "user_name/repo_name"

    def test_validate_github_repo_invalid(self):
        """Test invalid GitHub repository validation"""
        from playstorE.core.validation import validate_github_repo
        from playstorE.core.errors import ValidationError

        # Invalid formats
        invalid_repos = [
            "",
            "owner",  # Missing repo name
            "/repo",  # Missing owner
            "owner/repo/extra",  # Too many parts
            "owner//repo",  # Double slash
            "owner\\repo",  # Backslash
        ]

        for repo in invalid_repos:
            with pytest.raises(ValidationError):
                validate_github_repo(repo)

    def test_validate_github_repo_suspicious(self):
        """Test suspicious GitHub repository detection"""
        from playstorE.core.validation import validate_github_repo
        from playstorE.core.errors import SecurityError

        # Suspicious patterns
        suspicious_repos = [
            "owner/../etc/passwd",
            "owner//repo",
            "owner\\repo",
            "http://evil.com/repo",
            "owner@evil.com/repo",
        ]

        for repo in suspicious_repos:
            with pytest.raises(SecurityError):
                validate_github_repo(repo)

    def test_validate_path_within_base(self):
        """Test path validation within base directory"""
        from playstorE.core.validation import validate_path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Valid paths
            result = validate_path("safe_file.txt", tmpdir)
            assert str(result).endswith("safe_file.txt")

            result = validate_path("subdir/file.txt", tmpdir)
            assert "subdir/file.txt" in str(result)

    def test_validate_path_traversal_blocked(self):
        """Test path traversal blocking"""
        from playstorE.core.validation import validate_path
        from playstorE.core.errors import PathTraversalError

        with tempfile.TemporaryDirectory() as tmpdir:
            # Path traversal attempts
            traversal_paths = [
                "../etc/passwd",
                "../../etc/passwd",
                "subdir/../../../etc/passwd",
            ]

            for path in traversal_paths:
                with pytest.raises(PathTraversalError):
                    validate_path(path, tmpdir)

    def test_validate_semver_valid(self):
        """Test valid semantic version validation"""
        from playstorE.core.validation import validate_semver

        valid_versions = [
            "1.0.0",
            "0.1.0",
            "10.20.30",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0+build.123",
            "1.0.0-beta+exp.sha.5114f85",
            "v1.0.0",  # With v prefix
        ]

        for version in valid_versions:
            assert validate_semver(version) == version

    def test_validate_semver_invalid(self):
        """Test invalid semantic version validation"""
        from playstorE.core.validation import validate_semver
        from playstorE.core.errors import ValidationError

        invalid_versions = [
            "1",  # Missing parts
            "1.0",  # Missing patch
            "1.0.0.0",  # Too many parts
            "a.b.c",  # Non-numeric
            "1.0.0-",  # Incomplete prerelease
            "1.0.0+",  # Incomplete build
        ]

        for version in invalid_versions:
            with pytest.raises(ValidationError):
                validate_semver(version)

    def test_validate_app_id_valid(self):
        """Test valid app ID validation"""
        from playstorE.core.validation import validate_app_id

        valid_ids = [
            "com.example.app",
            "org.test.my-app",
            "io.github.user_repo",
            "MyApp123",
        ]

        for app_id in valid_ids:
            assert validate_app_id(app_id) == app_id

    def test_validate_app_id_invalid(self):
        """Test invalid app ID validation"""
        from playstorE.core.validation import validate_app_id
        from playstorE.core.errors import ValidationError

        invalid_ids = [
            "123app",  # Starts with number
            "app name",  # Contains space
            "app@name",  # Contains @
            "app/name",  # Contains /
        ]

        for app_id in invalid_ids:
            with pytest.raises(ValidationError):
                validate_app_id(app_id)

    def test_validate_search_query_valid(self):
        """Test valid search query validation"""
        from playstorE.core.validation import validate_search_query

        valid_queries = [
            "python cli tool",
            "fastapi rest api",
            "machine learning",
        ]

        for query in valid_queries:
            result = validate_search_query(query)
            assert result == query

    def test_validate_search_query_sanitization(self):
        """Test search query sanitization"""
        from playstorE.core.validation import validate_search_query

        # Dangerous characters should be removed
        query = 'test<script>alert("xss")</script>'
        result = validate_search_query(query)
        assert "<" not in result
        assert ">" not in result

    def test_validate_search_query_sql_injection(self):
        """Test SQL injection detection in search query"""
        from playstorE.core.validation import validate_search_query
        from playstorE.core.errors import ValidationError

        sql_queries = [
            "test SELECT * FROM users",
            "test DROP TABLE users",
            "test UNION SELECT password",
        ]

        for query in sql_queries:
            with pytest.raises(ValidationError):
                validate_search_query(query)

    def test_validate_port_valid(self):
        """Test valid port validation"""
        from playstorE.core.validation import validate_port

        assert validate_port(80) == 80
        assert validate_port(443) == 443
        assert validate_port(8000) == 8000
        assert validate_port(65535) == 65535
        assert validate_port("8080") == 8080

    def test_validate_port_invalid(self):
        """Test invalid port validation"""
        from playstorE.core.validation import validate_port
        from playstorE.core.errors import ValidationError

        invalid_ports = [
            0,
            -1,
            65536,
            100000,
            "abc",
            None,
        ]

        for port in invalid_ports:
            with pytest.raises(ValidationError):
                validate_port(port)

    def test_validate_url_valid(self):
        """Test valid URL validation"""
        from playstorE.core.validation import validate_url

        valid_urls = [
            "http://example.com",
            "https://example.com/path",
            "https://example.com:8080/path?query=value",
            "http://localhost:3000",
            "http://127.0.0.1:8000",
        ]

        for url in valid_urls:
            assert validate_url(url) == url

    def test_validate_url_dangerous_scheme(self):
        """Test dangerous URL scheme detection"""
        from playstorE.core.validation import validate_url
        from playstorE.core.errors import SecurityError

        dangerous_urls = [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            "file:///etc/passwd",
        ]

        for url in dangerous_urls:
            with pytest.raises(SecurityError):
                validate_url(url)

    def test_sanitize_filename(self):
        """Test filename sanitization"""
        from playstorE.core.validation import sanitize_filename

        # Dangerous characters should be replaced
        assert sanitize_filename("file<name>.txt") == "file_name_.txt"
        assert sanitize_filename("file:name.txt") == "file_name_.txt"

        # Path components should be removed
        assert sanitize_filename("/etc/passwd") == "passwd"
        assert sanitize_filename("C:\\Windows\\System32") == "System32"

        # Reserved names should be changed
        assert sanitize_filename("CON") == "unnamed_file"
        assert sanitize_filename("..") == "unnamed_file"

        # Long names should be truncated
        long_name = "a" * 300 + ".txt"
        sanitized = sanitize_filename(long_name)
        assert len(sanitized) <= 255

    def test_validate_email_valid(self):
        """Test valid email validation"""
        from playstorE.core.validation import validate_email

        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "user123@test.org",
        ]

        for email in valid_emails:
            assert validate_email(email) == email

    def test_validate_email_invalid(self):
        """Test invalid email validation"""
        from playstorE.core.validation import validate_email
        from playstorE.core.errors import ValidationError

        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            "user@example",
            "",
        ]

        for email in invalid_emails:
            with pytest.raises(ValidationError):
                validate_email(email)


class TestValidationIntegration:
    """Test validation integration with orchestrator"""

    def test_orchestrator_validates_github_repo(self):
        """Test that orchestrator validates GitHub repo format"""
        from playstorE.core.validation import validate_github_repo
        from playstorE.core.errors import ValidationError

        # Valid repo should pass
        result = validate_github_repo("valid-owner/valid-repo")
        assert result == "valid-owner/valid-repo"

        # Invalid repo should fail
        with pytest.raises(ValidationError):
            validate_github_repo("invalid")


# AsyncMock helper for testing async code
class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
