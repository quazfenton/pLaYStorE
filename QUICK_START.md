# AltStore Quick Start Guide

## 30-Second Overview

AltStore turns any GitHub repository into a one-click installable app with:
- **Automatic discovery** (GitHub API)
- **Security verification** (formal methods)
- **Reproducible builds** (bit-for-bit identical)
- **Offline installation** (air-gapped environments)
- **WASM fallback** (universal execution)

---

## Installation

```bash
# Clone the repository
git clone https://github.com/quazfenton/playstore.git
cd playstore

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/integration_test.py -v
```

---

## 5-Minute Tutorial

### 1. Search GitHub for Apps

```python
from playstorE.client.github_explorer import GitHubExplorer
import asyncio

async def discover():
    explorer = GitHubExplorer()

    # Search for ripgrep
    repos = await explorer.search_repos("ripgrep")
    for repo in repos:
        print(f"{repo.full_name}: {repo.stars} ⭐")

    # Analyze ripgrep
    analysis = await explorer.analyze_repo("BurntSushi/ripgrep")
    print(f"\nType: {analysis.repo_type.value}")
    print(f"Confidence: {analysis.confidence:.0%}")
    print(f"WASM Compatible: {analysis.wasm_compatible:.0%}")

asyncio.run(discover())
```

### 2. Validate Manifest

```python
from playstorE.core.types.manifest_schema import (
    AppManifest, Publisher, Source, Versions, Build, Run, RuntimeType,
    Security, Trust, ManifestValidator, NetworkPolicy, FilesystemPolicy
)

manifest = AppManifest(
    api_version="appstore.dev/v1",
    kind="Application",
    metadata={"app_id": "com.example.app", "name": "My App", "description": "Example application"},
    publisher=Publisher(name="Example", verified_domains=[]),
    source=Source(type="github_repo", repo="example/app"),
    versions=Versions(strategy="semver"),
    build=Build(strategy="docker"),
    run=Run(type=RuntimeType.CLI, entrypoint="app"),
    security=Security(
        sandbox="strict",
        network=NetworkPolicy.NONE,
        filesystem=FilesystemPolicy.READONLY
    ),
    trust=Trust(verification="none")
)

# Validate
is_valid = ManifestValidator.validate(manifest.to_dict())
print(f"Manifest valid: {is_valid}")
```

### 3. One-Click Install (Complete Workflow)

```python
from playstorE.core.orchestrator import PlatformOrchestrator
import asyncio

async def install():
    orchestrator = PlatformOrchestrator("./storage")

    # Complete workflow: GitHub → Installed App
    result = await orchestrator.discover_and_install(
        "BurntSushi/ripgrep",
        user_preferences={"allow_wasm": True}
    )

    if result["success"]:
        print("✅ Installation successful!")
        print(f"Install path: {result['install_result']['install_path']}")
        print(f"Trust score: {result['security']['trust_score']:.0%}")
        print(f"WASM available: {result['stages']['fallback_prep']['wasm_available']}")
    else:
        print(f"❌ Failed: {result['error']}")

asyncio.run(install())
```

### 4. Offline Installation (Air-Gapped)

```python
from playstorE.executor.offline_orchestrator import (
    OfflineCapsuleBuilder, OfflineInstallationManager
)

# On connected machine:
builder = OfflineCapsuleBuilder("./storage")
capsule_path = builder.build_offline_capsule(
    app_id="com.example.app",
    version="1.0.0",
    manifest={"example": "manifest"},
    native_artifacts=[("app", b"binary_content")],
    wasm_artifact=b"WASM_BINARY"
)
print(f"Created capsule: {capsule_path}")
# → Copy to USB drive

# On air-gapped machine:
installer = OfflineInstallationManager("./storage")
result = installer.install_from_capsule("/mnt/usb/capsule.cap")
print(f"Installed: {result['success']}")

# Run offline (no network needed)
trace = installer.run_app("com.example.app", "1.0.0")
print(f"Exit code: {trace.exit_code}")
print(f"Output: {trace.stdout}")
```

### 5. Generate UI

```python
from playstorE.client.frontend import MainUI, AppCard, TrustLevel

ui = MainUI()

# Add apps
ui.catalog.add_featured_app(AppCard(
    app_id="com.ripgrep.rg",
    name="ripgrep",
    description="Fast line search",
    publisher="BurntSushi",
    trust_level=TrustLevel.VERIFIED,
    stars=50000,
    tags=["CLI", "Rust", "Search"]
))

# Generate HTML file
ui.generate_html_file("index.html")
print("✓ UI generated: index.html")
```

---

## Common Tasks

### Search GitHub

```python
repos = await explorer.search_repos(
    "python",
    filters={
        "language": "Python",
        "min_stars": 100,
        "topics": ["cli"]
    },
    limit=10
)
```

### Analyze Repo

```python
analysis = await explorer.analyze_repo("owner/repo")
print(analysis.repo_type)           # CLI_TOOL, SERVER_APP, etc.
print(analysis.confidence)          # 0.0-1.0
print(analysis.wasm_compatible)     # 0.0-1.0
print(analysis.suggested_manifest)  # Ready-to-use manifest
```

### Check Trust Score

```python
security_mgr = SecurityManager()
assessment = security_mgr.assess_application(
    manifest,
    reproducibility_level="R2",
    malware_result="safe",
    community_score=0.8
)
print(f"Trust: {assessment['trust_score']:.0%}")
print(f"Sandbox: {assessment['security_policy']['sandbox']}")
```

### Build WASM Fallback

```python
wasm_mgr = WASMFallbackManager()

# Check compatibility
compat = wasm_mgr.compatibility_checker.check_compatibility(manifest)
print(f"WASM compatibility: {compat:.0%}")

# Build WASM
if wasm_mgr.should_use_wasm_fallback(manifest):
    wasm_file, config = wasm_mgr.prepare_wasm_execution(repo_path)
    success, stdout, stderr, code = wasm_mgr.execute_wasm_fallback(
        wasm_file, config, args=["--help"]
    )
    print(f"Exit code: {code}")
```

---

## Architecture at a Glance

```
GitHub Repo
    ↓ (GitHubExplorer)
Analyze & Classify
    ↓ (ManifestValidator)
Generate & Validate Manifest
    ↓ (FormalVerifier)
Verify Constraints (Z3)
    ↓ (SecurityManager)
Trust Score Assessment
    ↓ (ReproducibilityEngine)
Reproducible Build (R0-R3)
    ↓ (WASMFallbackManager)
WASM Compatibility Check
    ↓ (OfflineCapsuleBuilder)
Create Offline Capsule
    ↓ (OfflineInstallationManager)
Install from Capsule
    ↓ (Launcher)
Execute (Native or WASM)
```

---

## Configuration

### GitHub Token (Optional, for higher rate limits)

```python
explorer = GitHubExplorer(github_token="ghp_xxxxx")
```

### Storage Path

```python
orchestrator = PlatformOrchestrator("./my_storage")
```

### User Preferences

```python
result = await orchestrator.discover_and_install(
    "owner/repo",
    user_preferences={
        "allow_wasm": True,          # Enable WASM fallback
        "sandbox_level": "strict",   # strict, relaxed, trusted
        "allow_network": False       # Disable network access
    }
)
```

---

## Testing

```bash
# Run all integration tests
python -m pytest tests/integration_test.py -v

# Run specific component tests
python -m pytest tests/integration_test.py::TestGitHubDiscovery -v

# Run with coverage
python -m pytest tests/integration_test.py --cov=altstore --cov-report=html

# Run single test
python -m pytest tests/integration_test.py::TestManifestValidation::test_manifest_creation_and_validation -v
```

---

## Troubleshooting

### GitHub Rate Limit

```python
# Provide token for higher limits (5000/hour instead of 60/hour)
explorer = GitHubExplorer(github_token="ghp_xxxxx")
```

### WASM Not Available

```python
# Check compatibility
compat = wasm_mgr.compatibility_checker.check_compatibility(manifest)
if compat < 0.4:
    print("App not suitable for WASM")
```

### Capsule Verification Failed

```python
# Check offline trust data
snapshot = trust_mgr.get_latest_snapshot()
if not snapshot:
    print("No trust snapshot available - fetch while online first")
```

---

## Key Concepts

### Trust Levels
- 🔒 **Verified**: Signed by publisher, reproducible build
- 🟡 **Reproducible**: Open source, bit-for-bit identical
- 🔴 **Unverified**: Sandboxed only
- ⚪ **Unknown**: No trust data (offline mode)

### Reproducibility Levels
- **R0**: Not reproducible (mutable dependencies)
- **R1**: Deterministic inputs (locked versions)
- **R2**: Bit-for-bit identical (cryptographically verified)
- **R3**: Signed + reproducible (gold standard)

### Execution Modes
- **NATIVE**: Direct binary execution (fastest)
- **WASM**: Sandboxed WebAssembly (safe fallback)
- **CONTAINER**: Docker/OCI (when available)
- **OFFLINE**: Manual execution (for air-gapped)

---

## Examples Repository

Complete working examples in:
- `tests/integration_test.py` - All major features
- `client/github_explorer.py` - Docstring examples
- `executor/offline_orchestrator.py` - Offline flow
- `core/orchestrator.py` - Complete workflow

---

## Learn More

- **IMPLEMENTATION_GUIDE.md** - Full architecture explanation
- **FEATURES_IMPLEMENTED.md** - Complete feature inventory
- **README.md** - Project overview
- **DOCS.md** - Detailed documentation

---

## Community & Support

```
GitHub: https://github.com/quazfenton/playstore
Issues: Report bugs and feature requests
Discussions: Ask questions and share ideas
Contributing: Code, docs, testing welcome
```

---

## Next Steps

1. **Install & Test**: `pip install -r requirements.txt && pytest`
2. **Explore**: Run GitHub discovery examples
3. **Build**: Create offline capsules
4. **Deploy**: Set up REST API server
5. **Extend**: Add federation and governance

---

**Happy installing! 🚀**
