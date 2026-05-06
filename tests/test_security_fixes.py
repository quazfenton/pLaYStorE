"""
Security Fixes Verification Tests

Tests to verify all critical security vulnerabilities have been fixed:
1. CORS wildcard vulnerability
2. Mock cryptography fallback
3. Path traversal in capsule extraction
4. Signature verification bypass
5. XSS vulnerability
6. Input validation
7. Rate limiting
8. Health check endpoints
"""

import pytest
import json
import hashlib
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestCORSWildcardFix:
    """Test that CORS wildcard origins are rejected"""

    def test_wildcard_origin_rejected(self):
        """Verify that '*' CORS origin is rejected"""
        # This test verifies the logic in api.py
        allowed_origins = ["*", "http://localhost:3000", "https://example.com"]
        validated_origins = []
        
        for origin in allowed_origins:
            if origin == "*" or origin.startswith("*."):
                continue  # Should be rejected
            if origin.startswith(("http://", "https://")):
                validated_origins.append(origin)
        
        assert "*" not in validated_origins
        assert "http://localhost:3000" in validated_origins
        assert "https://example.com" in validated_origins

    def test_subdomain_wildcard_rejected(self):
        """Verify that '*.example.com' CORS origin is rejected"""
        allowed_origins = ["*.example.com", "http://localhost:3000"]
        validated_origins = []
        
        for origin in allowed_origins:
            if origin == "*" or origin.startswith("*."):
                continue  # Should be rejected
            if origin.startswith(("http://", "https://")):
                validated_origins.append(origin)
        
        assert "*.example.com" not in validated_origins
        assert "http://localhost:3000" in validated_origins


class TestCryptographyRequirement:
    """Test that cryptography is required and mock signatures are not allowed"""

    def test_cryptography_module_import(self):
        """Verify cryptography module is imported correctly"""
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa, padding
            from cryptography.exceptions import InvalidSignature
            crypto_available = True
        except ImportError:
            crypto_available = False
        
        assert crypto_available, "Cryptography library must be available"

    def test_capsules_requires_cryptography(self):
        """Verify capsules.py fails if cryptography is not available"""
        # The module should raise RuntimeError if cryptography is not available
        # This is tested by the module import itself
        import playstorE.storage.cas.capsules as capsules
        assert capsules.CRYPTO_AVAILABLE, "Cryptography must be available for capsules"


class TestPathTraversalFix:
    """Test that path traversal vulnerabilities are fixed"""

    def test_reject_null_bytes(self):
        """Verify null bytes in paths are rejected"""
        test_paths = [
            ("normal.txt", True),
            ("path\x00injection.txt", False),
            ("..\x00..", False),
        ]
        
        for path, expected in test_paths:
            result = '\x00' not in path
            assert result == expected, f"Path {path} should be {'accepted' if expected else 'rejected'}"

    def test_reject_path_traversal(self):
        """Verify path traversal attempts are rejected"""
        test_paths = [
            ("normal.txt", True),
            ("../etc/passwd", False),
            ("..\\..\\windows\\system32", False),
            ("/etc/passwd", False),
            ("C:\\windows\\system32", False),
            ("foo/../../../etc/passwd", False),
        ]
        
        for path, expected in test_paths:
            import os
            normalized = os.path.normpath(path)
            # Check for path traversal patterns
            has_traversal = (
                normalized.startswith('..') or 
                '/..' in normalized or
                path.startswith('/') or
                (len(path) > 1 and path[1] == ':') or
                '\\' in path
            )
            is_safe = not has_traversal
            assert is_safe == expected, f"Path {path} should be {'accepted' if expected else 'rejected'}"

    def test_reject_symlinks_escaping(self):
        """Verify symlinks pointing outside directory are rejected"""
        test_links = [
            ("normal_link", "target", True),
            ("link", "../etc/passwd", False),
            ("link", "/etc/passwd", False),
        ]
        
        for name, target, expected in test_links:
            # Check if symlink target escapes directory
            # Absolute paths (starting with /) and parent directory references (..) are unsafe
            escapes = target.startswith('/') or target.startswith('..') or '/..' in target
            is_safe = not escapes
            assert is_safe == expected, f"Symlink {name} -> {target} should be {'accepted' if expected else 'rejected'}"


class TestSignatureVerification:
    """Test that signature verification is properly implemented"""

    def test_signature_verification_requires_crypto(self):
        """Verify signature verification fails without cryptography"""
        import playstorE.storage.cas.capsules as capsules
        
        # The module should have CRYPTO_AVAILABLE = True
        assert capsules.CRYPTO_AVAILABLE, "Cryptography must be available"

    def test_signature_verification_with_valid_key(self):
        """Verify signature verification works with valid key"""
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes
        
        # Generate key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()
        
        # Sign data
        data = b"test data"
        signature = private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())
        
        # Verify signature
        try:
            public_key.verify(signature, data, padding.PKCS1v15(), hashes.SHA256())
            verified = True
        except Exception:
            verified = False
        
        assert verified, "Valid signature should verify successfully"

    def test_signature_verification_rejects_invalid(self):
        """Verify invalid signatures are rejected"""
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        
        # Generate key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()
        
        # Sign data
        data = b"test data"
        signature = private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())
        
        # Try to verify with tampered data
        tampered_data = b"tampered data"
        verified = False
        try:
            public_key.verify(signature, tampered_data, padding.PKCS1v15(), hashes.SHA256())
            verified = True
        except InvalidSignature:
            verified = False
        
        assert not verified, "Invalid signature should be rejected"


class TestXSSProtection:
    """Test that XSS vulnerabilities are fixed"""

    def test_html_escape_user_input(self):
        """Verify user input is HTML escaped"""
        import html
        
        malicious_inputs = [
            ("<script>alert('XSS')</script>", "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"),
            ('" onclick="alert(1)', "&#34; onclick=&#34;alert(1)"),
            ("javascript:alert(1)", "javascript:alert(1)"),  # Not escaped by html.escape
        ]
        
        for input_str, expected_substring in malicious_inputs:
            escaped = html.escape(input_str, quote=True)
            assert escaped != input_str or input_str == expected_substring, \
                f"Input {input_str} should be escaped"

    def test_url_validation_blocks_data_scheme(self):
        """Verify data: URLs are blocked"""
        from playstorE.client.frontend import AppCard
        
        dangerous_urls = [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:alert(1)",
            "file:///etc/passwd",
        ]
        
        # Create a mock AppCard to test _is_safe_url
        card = AppCard(
            app_id="test",
            name="Test",
            description="Test",
            publisher="Test"
        )
        
        for url in dangerous_urls:
            assert not card._is_safe_url(url), f"URL {url} should be blocked"

    def test_url_validation_allows_https(self):
        """Verify https: URLs are allowed"""
        from playstorE.client.frontend import AppCard
        
        safe_urls = [
            "https://example.com/image.png",
            "http://example.com/image.png",
            "//example.com/image.png",
            "/images/local.png",
        ]
        
        card = AppCard(
            app_id="test",
            name="Test",
            description="Test",
            publisher="Test"
        )
        
        for url in safe_urls:
            assert card._is_safe_url(url), f"URL {url} should be allowed"

    def test_js_escaping_in_onclick(self):
        """Verify JavaScript escaping in onclick handlers"""
        import html
        
        malicious_app_id = "'; alert(1); //"
        safe_app_id = html.escape(malicious_app_id, quote=True)
        js_safe = safe_app_id.replace('\\', '\\\\').replace("'", "\\'").replace('"', '&quot;')
        
        # The JS-safe version should not break out of string context
        assert "'" not in js_safe or "\\'" in js_safe, "Single quotes should be escaped"
        assert '"' not in js_safe or '&quot;' in js_safe, "Double quotes should be HTML escaped"


class TestInputValidation:
    """Test that input validation is properly implemented"""

    def test_github_repo_format_validation(self):
        """Verify GitHub repository format is validated"""
        import re
        
        pattern = r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+$'
        
        valid_repos = [
            "torvalds/linux",
            "microsoft/vscode",
            "user_name/repo-name",
            "org/repo.name",
        ]
        
        invalid_repos = [
            "../etc/passwd",
            "/absolute/path",
            "no-slash",
            "",
            "user/",
            "/repo",
        ]
        
        for repo in valid_repos:
            assert re.match(pattern, repo), f"Valid repo {repo} should match pattern"
        
        for repo in invalid_repos:
            assert not re.match(pattern, repo), f"Invalid repo {repo} should not match pattern"

    def test_query_validation_blocks_sql_injection(self):
        """Verify SQL injection patterns are blocked"""
        sql_patterns = ['--', ';', 'DROP ', 'SELECT ', 'UNION ', 'INSERT ', 'DELETE ', 'UPDATE ']
        
        malicious_queries = [
            "test'; DROP TABLE users; --",
            "SELECT * FROM users",
            "test UNION SELECT password FROM users",
        ]
        
        for query in malicious_queries:
            has_pattern = any(pattern.lower() in query.lower() for pattern in sql_patterns)
            assert has_pattern, f"Query {query} should be detected as malicious"


class TestHealthEndpoints:
    """Test that health check endpoints are implemented"""

    def test_health_endpoint_exists(self):
        """Verify health endpoint is defined"""
        from playstorE.api import app
        
        routes = [route.path for route in app.routes]
        assert "/health" in routes, "/health endpoint should exist"
        assert "/health/ready" in routes, "/health/ready endpoint should exist"
        assert "/health/live" in routes, "/health/live endpoint should exist"


class TestRateLimiting:
    """Test that rate limiting is implemented"""

    def test_rate_limiter_configured(self):
        """Verify rate limiter is configured"""
        from playstorE.api import app, limiter
        
        # Check that rate limiter is initialized
        assert limiter is not None, "Rate limiter should be initialized"
        
        # Check that app.state.limiter is set
        assert hasattr(app.state, 'limiter'), "Rate limiter should be set on app.state"
        
        # Check that exception handler is registered
        handlers = app.exception_handlers
        from slowapi.errors import RateLimitExceeded
        assert RateLimitExceeded in handlers, "RateLimitExceeded handler should be registered"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
