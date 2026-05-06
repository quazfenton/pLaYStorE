# Technical Implementation Plan

**Project:** AltStore/Playstore Platform  
**Date:** March 3, 2026  
**Status:** Production Readiness Audit  
**Review Reference:** `docs/review-results.md`  

---

## Executive Summary

This document outlines a prioritized, phased implementation plan to address **67 issues** identified during the comprehensive code review (8 Critical, 18 High, 28 Medium, 13 Low). The plan is structured into 4 phases over 12 weeks, with clear deliverables, success metrics, and rollback procedures for each phase.

### Current State
- **Production Readiness:** 3/10 🔴 Critical
- **Security Score:** 4/10 🔴 Critical
- **Test Coverage:** 18% 🔴 Critical
- **Estimated Effort:** 320 hours (8 weeks single developer, 4 weeks with 2 developers)

### Target State (After All Phases)
- **Production Readiness:** 9/10 ✅
- **Security Score:** 10/10 ✅
- **Test Coverage:** 80% ✅
- **Documentation:** Complete ✅

---

## Phase 1: Critical Security Fixes (Week 1-2)

**Goal:** Address all P0 Critical security vulnerabilities that block production deployment

**Duration:** 2 weeks  
**Effort:** 80 hours  
**Team:** 2 developers  

### P0-1: Fix CORS Wildcard Vulnerability

**Issue:** `allow_origins=["*"]` allows any origin - CSRF risk  
**File:** `playstorE/api.py` lines 14-19  
**Effort:** 1 hour  

**Implementation:**
```python
# playstorE/api.py
# Replace line 15:
allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")]
```

**Env Changes:**
```bash
# .env.example
FRONTEND_URL=http://localhost:3000
```

**Tests:**
```python
# tests/api/test_cors.py
def test_cors_allowed_origin():
    response = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"

def test_cors_disallowed_origin():
    response = client.get("/", headers={"Origin": "https://evil.com"})
    assert "Access-Control-Allow-Origin" not in response.headers
```

**Rollback:** Revert to `["*"]` temporarily if frontend breaks (not recommended)

---

### P0-2: Add Path Traversal Protection

**Issue:** `storage_path` not validated - could traverse outside intended directory  
**Files:** `playstorE/core/orchestrator.py`, `playstorE/api.py`  
**Effort:** 2 hours  

**Implementation:**
```python
# playstorE/core/orchestrator.py
def __init__(self, storage_path: str = "./altstore_storage", ...):
    from pathlib import Path
    import os
    
    # Validate and resolve storage path
    storage_path_obj = Path(storage_path).resolve()
    
    # Prevent path traversal - must be within current working directory
    if not str(storage_path_obj).startswith(os.getcwd()):
        raise ValueError(
            f"Storage path must be within current directory. "
            f"Got: {storage_path_obj}, CWD: {os.getcwd()}"
        )
    
    self.storage_path = storage_path_obj
    self.storage_path.mkdir(parents=True, exist_ok=True)
```

**Tests:**
```python
# tests/core/test_orchestrator_security.py
def test_storage_path_validation():
    with pytest.raises(ValueError, match="Storage path must be within"):
        orchestrator = PlatformOrchestrator(storage_path="/etc/passwd")
    
    with pytest.raises(ValueError, match="Storage path must be within"):
        orchestrator = PlatformOrchestrator(storage_path="../../../etc")
```

**Rollback:** Remove validation temporarily (security risk)

---

### P0-3: Fix Cryptography Mock Implementation

**Issue:** Mock cryptography when library unavailable - allows signature forgery  
**File:** `playstorE/storage/cas/capsules.py` lines 23-45  
**Effort:** 2 hours  

**Implementation:**
```python
# playstorE/storage/cas/capsules.py
# Replace lines 23-45:
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    # FAIL SECURELY - don't allow mock signatures
    raise RuntimeError(
        "cryptography library is required. Install with: pip install cryptography"
    )
```

**Requirements Update:**
```txt
# requirements.txt
cryptography>=41.0.0  # Required for secure capsule signatures
```

**Tests:**
```python
# tests/storage/test_crypto_required.py
def test_cryptography_import_error():
    # Simulate missing cryptography
    import sys
    original_modules = sys.modules.copy()
    sys.modules['cryptography'] = None
    
    # Should raise RuntimeError, not use mock
    with pytest.raises(RuntimeError, match="cryptography library is required"):
        # Re-import module
        import importlib
        import playstorE.storage.cas.capsules
        importlib.reload(playstorE.storage.cas.capsules)
    
    # Restore modules
    sys.modules.clear()
    sys.modules.update(original_modules)
```

**Rollback:** Restore mock (CRITICAL security risk - not recommended)

---

### P0-4: Fix Capsule Extraction Path Traversal

**Issue:** Path validation incomplete - extraction could escape intended directory  
**File:** `playstorE/executor/offline_orchestrator.py` lines 458-465  
**Effort:** 3 hours  

**Implementation:**
```python
# playstorE/executor/offline_orchestrator.py
def _extract_capsule(self, capsule_path: str, extract_dir: Path):
    import tarfile
    import os
    
    with tarfile.open(capsule_path, "r:gz") as tar:
        # CRITICAL: Validate ALL members BEFORE extracting ANY
        for member in tar.getmembers():
            # Normalize path to handle .. and symlinks
            member_path = os.path.normpath(member.name)
            
            # Reject path traversal attempts
            if member_path.startswith('..'):
                raise ValueError(f"Path traversal detected: {member.name}")
            
            # Reject absolute paths
            if os.path.isabs(member_path):
                raise ValueError(f"Absolute paths not allowed: {member.name}")
            
            # Reject Windows-style paths (cross-platform security)
            if '\\' in member_path:
                raise ValueError(f"Invalid path separator: {member.name}")
            
            # Additional check: ensure resolved path is within extract_dir
            resolved_path = (extract_dir / member_path).resolve()
            if not str(resolved_path).startswith(str(extract_dir.resolve())):
                raise ValueError(f"Path escapes extraction directory: {member.name}")
        
        # Only extract after ALL validations pass
        tar.extractall(extract_dir)
```

**Tests:**
```python
# tests/executor/test_capsule_security.py
def test_path_traversal_prevention():
    import tempfile
    import tarfile
    from io import BytesIO
    
    # Create malicious tarball with path traversal
    with tempfile.NamedTemporaryFile(suffix='.capsule') as f:
        with tarfile.open(f.name, 'w:gz') as tar:
            # Add file with path traversal
            info = tarfile.TarInfo(name='../../../etc/passwd')
            info.size = 10
            tar.addfile(info, BytesIO(b'0123456789'))
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Path traversal detected"):
            installer._extract_capsule(f.name, tempfile.mkdtemp())

def test_absolute_path_prevention():
    # Similar test for absolute paths
    pass
```

**Rollback:** Restore old extraction logic (CRITICAL security risk)

---

### P0-5: Fix Signature Verification Bypass

**Issue:** `_verify_snapshot_signature` always returns True  
**File:** `playstorE/storage/indexes/federated.py` lines 234-238  
**Effort:** 4 hours  

**Implementation:**
```python
# playstorE/storage/indexes/federated.py
def _verify_snapshot_signature(self, snapshot: Snapshot) -> bool:
    """Verify snapshot signature with actual cryptographic verification."""
    if not CRYPTO_AVAILABLE:
        # FAIL CLOSED - reject if crypto unavailable
        logger.error("Cryptography not available - cannot verify signature")
        return False
    
    try:
        # Reconstruct the exact data that was signed
        snapshot_data = {
            "apps": [self._serialize_app(app) for app in snapshot.apps],
            "timestamp": snapshot.timestamp,
            "node_id": snapshot.node_id,
            "previous_snapshot_hash": snapshot.previous_snapshot_hash
        }
        snapshot_json = json.dumps(snapshot_data, sort_keys=True)
        
        # Get publisher's public key from registry
        public_key = self._get_publisher_public_key(snapshot.node_id)
        if not public_key:
            logger.error(f"No public key found for node: {snapshot.node_id}")
            return False
        
        # Verify signature using cryptography library
        public_key.verify(
            bytes.fromhex(snapshot.signature),
            snapshot_json.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
        
    except InvalidSignature:
        logger.error(f"Invalid signature for snapshot from {snapshot.node_id}")
        return False
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False
```

**Tests:**
```python
# tests/storage/test_federated_security.py
def test_signature_verification_with_invalid_signature():
    # Create snapshot with invalid signature
    snapshot = Snapshot(
        apps=[],
        timestamp="2026-03-03T00:00:00Z",
        signature="invalid_signature_hex",
        node_id="test_node"
    )
    
    # Should return False for invalid signature
    assert node._verify_snapshot_signature(snapshot) is False
```

**Rollback:** Restore `return True` (CRITICAL security risk)

---

### P0-6: Add Rate Limiting to API

**Issue:** No rate limiting - DoS vulnerability  
**File:** `playstorE/api.py` all endpoints  
**Effort:** 4 hours  

**Implementation:**
```python
# requirements.txt addition
slowapi>=0.1.9

# playstorE/api.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Add exception handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add to each endpoint:
@app.post("/search")
@limiter.limit("100/minute")
async def search_repos(request: Request, search_request: SearchRequest):
    # ... existing code
```

**Env Changes:**
```bash
# .env.example
RATE_LIMIT_SEARCH=100/minute
RATE_LIMIT_ANALYZE=30/minute
RATE_LIMIT_INSTALL=10/minute
```

**Tests:**
```python
# tests/api/test_rate_limiting.py
def test_search_rate_limiting():
    # Make 101 requests rapidly
    for i in range(100):
        response = client.post("/search", json={"query": "test"})
        assert response.status_code == 200
    
    # 101st request should be rate limited
    response = client.post("/search", json={"query": "test"})
    assert response.status_code == 429
```

**Rollback:** Remove `@limiter.limit` decorators temporarily

---

### P0-7: Implement Workflow Persistence

**Issue:** Workflows lost on restart - no persistence  
**File:** `playstorE/api.py` lines 27-28  
**Effort:** 8 hours  

**Implementation:**
```python
# New file: playstorE/storage/workflow_store.py
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class WorkflowStore:
    """Persistent workflow storage using JSON files."""
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.workflows_dir = self.storage_path / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_workflow_path(self, workflow_id: str) -> Path:
        return self.workflows_dir / f"{workflow_id}.json"
    
    def __setitem__(self, workflow_id: str, data: Dict[str, Any]):
        """Save workflow to disk."""
        data['_updated_at'] = datetime.utcnow().isoformat()
        path = self._get_workflow_path(workflow_id)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def __getitem__(self, workflow_id: str) -> Dict[str, Any]:
        """Load workflow from disk."""
        path = self._get_workflow_path(workflow_id)
        if not path.exists():
            raise KeyError(f"Workflow {workflow_id} not found")
        with open(path, 'r') as f:
            return json.load(f)
    
    def __contains__(self, workflow_id: str) -> bool:
        """Check if workflow exists."""
        return self._get_workflow_path(workflow_id).exists()
    
    def __delitem__(self, workflow_id: str):
        """Delete workflow."""
        path = self._get_workflow_path(workflow_id)
        if path.exists():
            path.unlink()
    
    def cleanup_old_workflows(self, max_age_days: int = 7):
        """Remove workflows older than max_age_days."""
        cutoff = datetime.utcnow().timestamp() - (max_age_days * 24 * 60 * 60)
        for path in self.workflows_dir.glob("*.json"):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                updated_at = datetime.fromisoformat(data.get('_updated_at', '')).timestamp()
                if updated_at < cutoff:
                    path.unlink()
            except Exception:
                pass  # Skip corrupted files
```

**Update api.py:**
```python
# playstorE/api.py
from playstorE.storage.workflow_store import WorkflowStore

# Replace line 28:
# workflows = {}
workflows = WorkflowStore(storage_path="./data/workflows")
```

**Tests:**
```python
# tests/storage/test_workflow_store.py
def test_workflow_persistence():
    store = WorkflowStore("./test_data")
    
    # Save workflow
    store["wf_test"] = {"status": "running", "progress": 50}
    
    # Reload from disk
    loaded = store["wf_test"]
    assert loaded["status"] == "running"
    assert loaded["progress"] == 50
    assert "_updated_at" in loaded
```

**Rollback:** Restore `workflows = {}` (data loss on restart)

---

### P0-8: Fix XSS Vulnerability in Frontend

**Issue:** URL sanitization incomplete - data: URLs possible  
**File:** `playstorE/client/frontend.py` lines 98-105  
**Effort:** 2 hours  

**Implementation:**
```python
# playstorE/client/frontend.py
class AppCard:
    def _is_safe_url(self, url: str) -> bool:
        """Validate URL is safe for rendering."""
        if not url:
            return False
        
        url_lower = url.lower().strip()
        
        # Block dangerous schemes
        dangerous_schemes = [
            'javascript:', 'data:', 'vbscript:', 'file:',
            'blob:', 'about:', 'moz-extension:'
        ]
        if any(url_lower.startswith(scheme) for scheme in dangerous_schemes):
            return False
        
        # Allow only http, https, and protocol-relative
        if url_lower.startswith(('http://', 'https://', '//')):
            return True
        
        # Allow relative URLs that don't start with dangerous patterns
        if not url_lower.startswith(('javascript:', 'data:', 'vbscript:')):
            return True
        
        return False
    
    def to_html(self) -> str:
        # ... existing code ...
        
        # Sanitize icon URL
        safe_icon_url = None
        if self.icon_url and self._is_safe_url(self.icon_url):
            safe_icon_url = html.escape(self.icon_url, quote=True)
```

**Tests:**
```python
# tests/client/test_frontend_security.py
def test_safe_url_validation():
    card = AppCard(...)
    
    # Dangerous URLs should be rejected
    assert card._is_safe_url("javascript:alert(1)") is False
    assert card._is_safe_url("data:text/html,<script>alert(1)</script>") is False
    assert card._is_safe_url("file:///etc/passwd") is False
    
    # Safe URLs should be accepted
    assert card._is_safe_url("https://example.com/icon.png") is True
    assert card._is_safe_url("//cdn.example.com/icon.png") is True
```

**Rollback:** Restore old URL handling (security risk)

---

## Phase 2: Core Functionality (Week 3-6)

**Goal:** Complete missing implementations and fix high-priority issues

**Duration:** 4 weeks  
**Effort:** 160 hours  
**Team:** 2 developers  

### P1-1: Implement Build Stage

**Issue:** Build stage raises NotImplementedError  
**File:** `playstorE/core/orchestrator.py` lines 183-192  
**Effort:** 16 hours  

**Implementation:**
```python
# playstorE/core/orchestrator.py
async def _stage_build(self, manifest: Dict) -> Optional[Dict]:
    """Build application with Docker-based reproducible builds."""
    import asyncio
    import hashlib
    from pathlib import Path
    
    try:
        logger.info(f"Starting build for {manifest.get('metadata', {}).get('app_id')}")
        
        # Get build configuration from manifest
        build_config = manifest.get('build', {})
        strategy = build_config.get('strategy', 'script')
        commands = build_config.get('commands', [])
        base_image = build_config.get('base_image')
        environment = build_config.get('environment', {})
        
        # Create build directory
        build_dir = Path(tempfile.mkdtemp(prefix="altstore_build_"))
        
        try:
            # Execute build based on strategy
            if strategy == 'docker':
                result = await self._build_with_docker(
                    build_dir, commands, base_image, environment
                )
            elif strategy == 'script':
                result = await self._build_with_script(
                    build_dir, commands, environment
                )
            elif strategy == 'cargo':
                result = await self._build_with_cargo(
                    build_dir, commands, environment
                )
            elif strategy == 'npm':
                result = await self._build_with_npm(
                    build_dir, commands, environment
                )
            else:
                result = await self._build_with_script(
                    build_dir, commands, environment
                )
            
            # Calculate build hash
            build_hash = self._calculate_build_hash(build_dir)
            
            return {
                "success": True,
                "hash": build_hash,
                "output_dir": str(build_dir),
                "reproducibility_level": "R1",  # Would be calculated
                "log": result.get('log', ''),
                "duration_seconds": result.get('duration', 0)
            }
            
        finally:
            # Cleanup build directory (or keep for caching)
            # shutil.rmtree(build_dir, ignore_errors=True)
            pass
            
    except Exception as e:
        logger.error(f"Build failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "hash": None,
            "output_dir": None
        }

async def _build_with_docker(self, build_dir: Path, commands: List[str], 
                            base_image: str, environment: Dict) -> Dict:
    """Build using Docker for reproducibility."""
    import asyncio
    
    # Create Dockerfile
    dockerfile_content = f"""
FROM {base_image or 'python:3.11-slim'}
WORKDIR /app
COPY . .
RUN {" && ".join(commands)}
"""
    (build_dir / "Dockerfile").write_text(dockerfile_content)
    
    # Build Docker image
    try:
        process = await asyncio.create_subprocess_exec(
            'docker', 'build', '-t', 'altstore-build', '.',
            cwd=build_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        return {
            'success': process.returncode == 0,
            'log': stdout.decode() + stderr.decode(),
            'duration': 0  # Would track actual time
        }
    except Exception as e:
        return {
            'success': False,
            'log': str(e),
            'duration': 0
        }
```

**Tests:**
```python
# tests/core/test_build_stage.py
async def test_build_stage_docker():
    orchestrator = PlatformOrchestrator()
    manifest = {
        "build": {
            "strategy": "docker",
            "commands": ["echo 'test'"],
            "base_image": "python:3.11-slim"
        }
    }
    
    result = await orchestrator._stage_build(manifest)
    assert result is not None
    assert "success" in result
```

---

[Additional P1 and P2 tasks follow same pattern...]

---

## Phase 3: Testing & Quality (Week 7-10)

**Goal:** Achieve 80% test coverage and add comprehensive documentation

**Duration:** 4 weeks  
**Effort:** 160 hours  

### Test Coverage Goals

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| api.py | 0% | 80% | P0 |
| orchestrator.py | 10% | 80% | P0 |
| manifest_schema.py | 40% | 90% | P1 |
| formal_verifier.py | 20% | 80% | P1 |
| trust_model.py | 15% | 80% | P1 |
| reproducible_builds.py | 10% | 80% | P1 |
| offline_orchestrator.py | 25% | 80% | P0 |
| wasm.py | 20% | 80% | P2 |
| sandbox/base.py | 30% | 80% | P2 |
| capsules.py | 20% | 80% | P0 |
| federated.py | 10% | 80% | P0 |
| github_explorer.py | 25% | 80% | P1 |
| frontend.py | 5% | 70% | P2 |

### CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11"]

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio
    
    - name: Lint with flake8
      run: |
        pip install flake8
        flake8 playstorE/ tests/
    
    - name: Type check with mypy
      run: |
        pip install mypy
        mypy playstorE/ --ignore-missing-imports
    
    - name: Test with pytest
      run: |
        pytest --cov=playstorE --cov-report=xml --cov-fail-under=80
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Phase 4: Advanced Features (Week 11-12)

**Goal:** Implement advanced features and optimizations

**Duration:** 2 weeks  
**Effort:** 80 hours  

[Advanced features implementation plan...]

---

## Environment Variables Summary

Add to `.env.example`:

```bash
# ================================
# AltStore Platform Configuration
# ================================

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_URL=http://localhost:3000

# GitHub API
GITHUB_TOKEN=
GITHUB_API_TIMEOUT=30

# Rate Limiting
RATE_LIMIT_SEARCH=100/minute
RATE_LIMIT_ANALYZE=30/minute
RATE_LIMIT_INSTALL=10/minute

# Storage
ALTSTORE_STORAGE=./altstore_storage
WORKFLOW_STORAGE=./data/workflows

# Security
MASTER_KEY=  # 32+ bytes for encryption (generate with: openssl rand -hex 32)
SECRET_KEY=  # For JWT/session (generate with: openssl rand -hex 32)

# Cryptography
CRYPTOGRAPHY_REQUIRED=true

# Timeouts
BUILD_TIMEOUT=300
INSTALL_TIMEOUT=600
WASM_TIMEOUT=30

# Feature Flags
ENABLE_WASM_FALLBACK=true
ENABLE_OFFLINE_CAPSULES=true
ENABLE_FEDERATED_INDEX=false

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Rollback Plan

### General Rollback Procedure

1. **Identify Issue:** Determine which change caused the problem
2. **Assess Impact:** Evaluate severity and user impact
3. **Communicate:** Notify stakeholders of rollback
4. **Execute Rollback:**
   ```bash
   git revert <commit-hash>
   git push origin main
   ```
5. **Verify:** Confirm system stability after rollback
6. **Post-Mortem:** Document root cause and prevention

### Phase-Specific Rollback

| Phase | Rollback Complexity | Risk | Notes |
|-------|-------------------|------|-------|
| Phase 1 (Security) | High | Critical | Security fixes should NOT be rolled back except temporarily |
| Phase 2 (Core) | Medium | High | Build stage can fallback to mock |
| Phase 3 (Testing) | Low | None | Tests are additive, no rollback needed |
| Phase 4 (Advanced) | Low | Low | Feature flags allow gradual rollback |

---

## Success Metrics

### Phase 1 Success Criteria
- [ ] All 8 Critical issues resolved
- [ ] Security score improved from 4/10 to 7/10
- [ ] Zero known path traversal vulnerabilities
- [ ] Cryptography required and enforced
- [ ] Rate limiting active on all endpoints

### Phase 2 Success Criteria
- [ ] All 18 High issues resolved
- [ ] Build stage functional
- [ ] Workflow persistence working
- [ ] Production readiness improved to 6/10

### Phase 3 Success Criteria
- [ ] Test coverage ≥ 80%
- [ ] All critical paths tested
- [ ] CI/CD pipeline operational
- [ ] Documentation complete

### Phase 4 Success Criteria
- [ ] All 28 Medium issues resolved
- [ ] Advanced features implemented
- [ ] Production readiness ≥ 9/10
- [ ] Ready for production deployment

---

## Resource Requirements

### Development Team
- 2 Senior Python Developers (full-time, 12 weeks)
- 1 Frontend Developer (part-time, 4 weeks)
- 1 DevOps Engineer (part-time, 2 weeks)

### Infrastructure
- Development environment with Docker
- CI/CD pipeline (GitHub Actions)
- Test database (PostgreSQL)
- Staging environment

### Total Estimated Cost
- Development: $96,000 (320 hours × $150/hour blended rate)
- Infrastructure: $500/month
- **Total: ~$98,000**

---

## Next Steps

1. **Immediate (This Week):**
   - [ ] Review and approve this technical plan
   - [ ] Set up development environment
   - [ ] Begin Phase 1 implementation

2. **Week 1:**
   - [ ] Complete P0-1 through P0-4
   - [ ] Daily standups to track progress
   - [ ] End-of-week security review

3. **Week 2:**
   - [ ] Complete P0-5 through P0-8
   - [ ] Phase 1 retrospective
   - [ ] Begin Phase 2 planning

---

**Document Created:** March 3, 2026  
**Last Updated:** March 3, 2026  
**Status:** Ready for Implementation  
**Approval Required:** Yes (Security Team + Engineering Lead)
