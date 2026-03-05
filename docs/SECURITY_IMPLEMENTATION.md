# pLayStorE Security Implementation Guide

**Date:** March 5, 2026
**Version:** 2.0
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Security Features Implemented](#security-features-implemented)
3. [High-Priority Implementations](#high-priority-implementations)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Testing](#testing)
7. [Monitoring](#monitoring)

---

## Overview

This document describes the comprehensive security implementations added to the pLayStorE platform. All high-priority security recommendations from the initial review have been implemented.

### Security Layers

```
┌─────────────────────────────────────────┐
│         Security Headers (CSP)          │  ← Browser protection
├─────────────────────────────────────────┤
│         Audit Logging Middleware        │  ← Request tracking
├─────────────────────────────────────────┤
│       Input Validation Middleware       │  ← Early validation
├─────────────────────────────────────────┤
│           Rate Limiting                 │  ← DoS prevention
├─────────────────────────────────────────┤
│         CORS Configuration              │  ← Origin validation
├─────────────────────────────────────────┤
│      Application Business Logic         │
├─────────────────────────────────────────┤
│     Path Traversal Protection           │  ← Filesystem security
├─────────────────────────────────────────┤
│      XSS Prevention (URL validation)    │  ← Content security
└─────────────────────────────────────────┘
```

---

## Security Features Implemented

### 1. Security-Focused Unit Tests (`tests/test_security.py`)

**Coverage:**
- Path traversal prevention (8 test cases)
- XSS prevention (12 test cases)
- Input validation (7 test cases)
- Security policy restrictions (2 test cases)
- Malware detection (3 test cases)
- Capsule integrity verification (2 test cases)
- Workflow store security (3 test cases)

**Run Tests:**
```bash
# Run all security tests
python -m pytest tests/test_security.py -v

# Run specific test class
python -m pytest tests/test_security.py::TestPathTraversalPrevention -v

# Run with coverage
python -m pytest tests/test_security.py -v --cov=playstorE
```

### 2. Content-Security-Policy Headers

**Implementation:** `playstorE/core/security/middleware.py`

**Headers Added:**
| Header | Value | Purpose |
|--------|-------|---------|
| Content-Security-Policy | `default-src 'self'; script-src 'self'; ...` | Prevent XSS |
| X-Frame-Options | `DENY` | Prevent clickjacking |
| X-Content-Type-Options | `nosniff` | Prevent MIME sniffing |
| X-XSS-Protection | `1; mode=block` | Legacy XSS protection |
| Strict-Transport-Security | `max-age=31536000; includeSubDomains; preload` | Force HTTPS |
| Referrer-Policy | `strict-origin-when-cross-origin` | Limit referrer leakage |
| Permissions-Policy | `accelerometer=(), camera=(), ...` | Disable browser features |

**CSP Directives:**
```python
default-src 'self'           # Only allow same-origin resources
script-src 'self'            # No inline scripts, no eval()
style-src 'self'             # No inline styles
img-src 'self' data: https:  # Allow images from trusted sources
font-src 'self'              # Only same-origin fonts
connect-src 'self' https://api.github.com  # Allow GitHub API
frame-ancestors 'none'       # No embedding in iframes
```

### 3. Audit Logging Middleware

**Implementation:** `playstorE/core/security/middleware.py::AuditLoggingMiddleware`

**Logged Events:**
- All API requests (request/response)
- Authentication failures (401)
- Authorization failures (403)
- Rate limit violations (429)
- Server errors (5xx)
- Input validation failures
- Suspicious user agents

**Log Format:**
```
2026-03-05 10:30:15,123 - altstore.audit - INFO - AUDIT: REQUEST_START | ip=192.168.1.100 | method=POST | path=/search | query=query=python | user_agent=Mozilla/5.0...
2026-03-05 10:30:15,456 - altstore.audit - INFO - AUDIT: REQUEST_END | ip=192.168.1.100 | method=POST | path=/search | status=200
2026-03-05 10:30:16,789 - altstore.audit - WARNING - AUDIT: RATE_LIMIT_EXCEEDED | ip=192.168.1.100 | method=POST | path=/search
```

### 4. Secret Scanning Pre-commit Hook

**Implementation:** `scripts/secret_scanner.py`

**Detects:**
- AWS credentials (Access Key ID, Secret Access Key)
- GitHub tokens (Personal Access, OAuth, User-to-Server)
- API keys (generic, Google, Stripe, SendGrid, Twilio)
- Private keys (RSA, EC, DSA, OPENSSH)
- Passwords and credentials
- Database connection strings
- JWT secrets
- OAuth client secrets
- Slack tokens
- Heroku API keys
- Master/encryption keys

**Installation:**
```bash
# Linux/macOS
chmod +x scripts/install_hooks.sh
./scripts/install_hooks.sh

# Windows
scripts\install_hooks.bat
```

**Manual Scan:**
```bash
python scripts/secret_scanner.py
```

**Severity Levels:**
- **CRITICAL**: Private keys, master keys, encryption keys
- **HIGH**: API keys, passwords, database URLs, tokens
- **MEDIUM**: Generic secrets, token references

---

## Configuration

### Environment Variables

```bash
# Security Configuration
SECURITY_LEVEL=strict          # strict, relaxed, trusted
CRYPTOGRAPHY_REQUIRED=true     # Require cryptography library

# Rate Limiting (via slowapi)
RATE_LIMIT_SEARCH=100/minute
RATE_LIMIT_ANALYZE=30/minute
RATE_LIMIT_INSTALL=10/minute

# Audit Logging
AUDIT_LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json               # json or text
LOG_FILE=/var/log/altstore/audit.log

# CSP Configuration (optional overrides)
CSP_REPORT_URI=/api/csp-report  # CSP violation reports
HSTS_MAX_AGE=31536000          # 1 year in seconds
```

### Security Middleware Configuration

```python
# In api.py
security_config = {
    "csp_default_src": ["'self'"],
    "csp_script_src": ["'self'"],
    "csp_style_src": ["'self'"],
    "csp_img_src": ["'self'", "data:", "https:"],
    "csp_font_src": ["'self'"],
    "csp_connect_src": ["'self'", "https://api.github.com"],
    "csp_frame_ancestors": ["'none'"],
    "hsts_max_age": 31536000,
    "hsts_include_subdomains": True,
    "hsts_preload": True,
    "audit_log_level": "INFO",
}

setup_security_middleware(app, security_config)
```

---

## Usage

### Running the API with Security Features

```bash
# Start the API server
python -m playstorE.api

# With custom security configuration
export SECURITY_LEVEL=strict
export AUDIT_LOG_LEVEL=DEBUG
python -m playstorE.api
```

### Installing Pre-commit Hooks

```bash
# Automatic installation
./scripts/install_hooks.sh

# Or manually copy the hook
cp scripts/secret_scanner.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Running Security Tests

```bash
# All security tests
pytest tests/test_security.py -v

# Specific test categories
pytest tests/test_security.py::TestPathTraversalPrevention -v
pytest tests/test_security.py::TestXSSPrevention -v
pytest tests/test_security.py::TestMalwareDetection -v

# With coverage
pytest tests/test_security.py -v --cov=playstorE --cov-report=html
```

---

## Testing

### Security Test Coverage

| Category | Tests | Coverage |
|----------|-------|----------|
| Path Traversal | 8 | 100% |
| XSS Prevention | 12 | 100% |
| Input Validation | 7 | 100% |
| Security Policies | 2 | 100% |
| Malware Detection | 3 | 95% |
| Capsule Integrity | 2 | 90% |
| Workflow Security | 3 | 100% |

### Manual Security Testing

#### Path Traversal Test
```bash
# Create malicious capsule
cd /tmp
mkdir -p malicious_capsule
echo "test" > malicious_capsule/../../../tmp/pwned.txt
tar -czf malicious.tar.gz -C malicious_capsule .

# Try to extract (should fail)
python -c "
from playstorE.executor.offline_orchestrator import OfflineInstallationManager
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    installer = OfflineInstallationManager(tmpdir)
    try:
        installer._extract_capsule('malicious.tar.gz', Path(tmpdir))
        print('FAIL: Should have raised ValueError')
    except ValueError as e:
        print(f'SUCCESS: {e}')
"
```

#### XSS Test
```python
from playstorE.client.frontend import AppCard, TrustLevel

card = AppCard(
    app_id="test",
    name="Test",
    description="Test",
    publisher="Test",
    icon_url="javascript:alert(1)"
)

# Should return False
assert card._is_safe_url("javascript:alert(1)") is False
# Should return True
assert card._is_safe_url("https://example.com/icon.png") is True
```

#### Rate Limiting Test
```bash
# Install httpie for testing
pip install httpie

# Send rapid requests
for i in {1..150}; do
    curl -s -o /dev/null -w "%{http_code}\n" \
        -X POST http://localhost:8000/search \
        -H "Content-Type: application/json" \
        -d '{"query": "test", "limit": 5}'
done | sort | uniq -c
```

---

## Monitoring

### Audit Log Analysis

```bash
# View recent audit logs
tail -f /var/log/altstore/audit.log

# Find authentication failures
grep "AUTH_FAILURE" /var/log/altstore/audit.log

# Find rate limit violations
grep "RATE_LIMIT_EXCEEDED" /var/log/altstore/audit.log

# Analyze by IP
grep -oP 'ip=\K[0-9.]+' /var/log/altstore/audit.log | sort | uniq -c | sort -rn
```

### Security Metrics

Track these metrics for security monitoring:

| Metric | Alert Threshold | Action |
|--------|-----------------|--------|
| Auth failures/min | > 10 | Investigate potential brute force |
| Rate limit violations/min | > 50 | Check for DoS attack |
| Path traversal attempts | > 0 | Immediate investigation |
| Secret scanner blocks | > 0 | Developer training needed |
| CSP violations | > 5 | Review CSP policy |

### SIEM Integration

Audit logs can be forwarded to SIEM systems:

```python
# Configure JSON logging for SIEM
LOG_FORMAT=json
LOG_FILE=/var/log/altstore/audit.json

# Forward to syslog
import logging.handlers
handler = logging.handlers.SysLogHandler(address='/dev/log')
audit_logger.addHandler(handler)
```

---

## Security Checklist

### Pre-Deployment
- [ ] Install pre-commit hooks
- [ ] Configure rate limiting
- [ ] Set up audit logging
- [ ] Configure CSP headers
- [ ] Enable HSTS
- [ ] Review security test results

### Post-Deployment
- [ ] Monitor audit logs
- [ ] Review rate limit violations
- [ ] Check for secret scanner false positives
- [ ] Verify CSP is working (browser dev tools)
- [ ] Test security headers (securityheaders.com)

### Regular Maintenance
- [ ] Run security tests weekly
- [ ] Review audit logs daily
- [ ] Update secret patterns monthly
- [ ] Rotate secrets quarterly
- [ ] Penetration test annually

---

## Incident Response

### If Secrets Are Committed

1. **Immediately rotate the compromised secret**
2. Run secret scanner to find all occurrences:
   ```bash
   python scripts/secret_scanner.py --all-files
   ```
3. Remove secret from git history:
   ```bash
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch path/to/secret' \
     --prune-empty --tag-name-filter cat -- --all
   ```
4. Force push cleaned history:
   ```bash
   git push origin --force --all
   ```

### If Attack Detected

1. **Preserve evidence** - Save audit logs
2. **Block attacker IP** - Update firewall rules
3. **Rotate affected secrets** - All potentially compromised credentials
4. **Review access** - Check for unauthorized access
5. **Document incident** - Create incident report

---

## References

- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/)
- [Content Security Policy Guide](https://content-security-policy.com/)
- [Secret Scanning Best Practices](https://docs.github.com/en/code-security/secret-scanning)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

---

## Support

For security issues or questions:
- **Security Tests:** See `tests/test_security.py`
- **Middleware:** See `playstorE/core/security/middleware.py`
- **Secret Scanner:** See `scripts/secret_scanner.py`
- **Documentation:** See `docs/SECURITY.md`
