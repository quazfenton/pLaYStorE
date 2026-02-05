# AltStore Implementation Guide

## Overview

This document explains how all components work together to create an **Alternative App Store + Universal Installer/Launcher** that:

1. **Discovers** GitHub projects automatically
2. **Analyzes** repos to classify and validate them
3. **Builds** reproducibly with WASM fallback
4. **Packages** into offline-first capsules
5. **Installs** with zero network (air-gapped support)
6. **Executes** with intelligent fallback chains

## Architecture

```
GitHub Repository
      ↓
┌─────────────────────────────────┐
│ GitHub Explorer                 │  (client/github_explorer.py)
│ - Search & discovery            │
│ - README parsing                │
│ - Repo classification           │
└──────────┬──────────────────────┘
           ↓
┌─────────────────────────────────┐
│ Formal Manifest Generator       │  (core/types/manifest_schema.py)
│ - Auto-manifest from analysis   │
│ - Schema validation             │
│ - Formal verification (Z3/SMT)  │
└──────────┬──────────────────────┘
           ↓
┌─────────────────────────────────┐
│ Security Assessment             │  (core/security/*)
│ - Malware detection             │
│ - Trust scoring                 │
│ - Reproducibility check         │
└──────────┬──────────────────────┘
           ↓
┌─────────────────────────────────┐
│ Reproducible Build System       │  (core/security/reproducible_builds.py)
│ - Docker-isolated builds        │
│ - Deterministic R0-R3 levels    │
│ - Native artifact generation    │
└──────────┬──────────────────────┘
           ↓
┌─────────────────────────────────┐
│ WASM Fallback Preparation       │  (executor/wasm.py)
│ - Compatibility checking        │
│ - Language-specific builders    │
│ - Safe sandbox config           │
└──────────┬──────────────────────┘
           ↓
┌─────────────────────────────────┐
│ Offline Capsule Builder         │  (executor/offline_orchestrator.py)
│ - Content-addressed storage     │
│ - Capsule signing               │
│ - Trust snapshots               │
│ - Artifact deduplication        │
└──────────┬──────────────────────┘
           ↓
┌─────────────────────────────────┐
│ Offline Installation Manager    │  (executor/offline_orchestrator.py)
│ - Zero-network install          │
│ - Capsule verification          │
│ - Execution mode selection      │
└──────────┬──────────────────────┘
           ↓
┌─────────────────────────────────┐
│ Application Launcher            │  (executor/offline_orchestrator.py)
│ - Native execution              │
│ - WASM fallback chains          │
│ - Execution tracing             │
└──────────┬──────────────────────┘
           ↓
Running Application (Native / WASM / Sandboxed)
```

## Component Details

### 1. GitHub Explorer (`client/github_explorer.py`)

**Transforms GitHub URLs into runnable apps**

```python
from altstore.client.github_explorer import GitHubExplorer

explorer = GitHubExplorer(github_token="your_token")

# Search GitHub
repos = await explorer.search_repos("cli", filters={"language": "Rust"})

# Analyze specific repo
analysis = await explorer.analyze_repo("BurntSushi/ripgrep")
print(analysis.repo_type)          # RepoType.CLI_TOOL
print(analysis.suggested_manifest)  # Ready-to-use manifest dict
```

**Key Features:**
- Search GitHub API with filters (language, stars, topics)
- Auto-classify repos (CLI, Server, Desktop, AI, etc.)
- Extract run instructions from README
- Detect ports and entrypoints
- Safety risk assessment
- WASM compatibility scoring

**Output:** `RepositoryAnalysis` with:
- Repo metadata
- Type classification & confidence
- Build strategy recommendations
- Suggested manifest (auto-generated)
- Trust/safety assessment

---

### 2. Manifest Schema & Validation (`core/types/manifest_schema.py`)

**Universal, cross-platform app definition**

```python
from altstore.core.types.manifest_schema import AppManifest, ManifestValidator

# Create manifest
manifest = AppManifest(
    api_version="appstore.dev/v1",
    kind="Application",
    metadata={"app_id": "com.example.app", "name": "My App"},
    # ... all other fields
)

# Validate
ManifestValidator.validate(manifest.to_dict())  # Raises if invalid

# Formal verification (SMT)
from altstore.core.validation.formal_verifier import FormalVerifier
verifier = FormalVerifier()
result = verifier.verify_manifest(manifest.to_dict())
# Checks: network=true only if reproducibility>=R2, GPU only in certain modes, etc.
```

**Schema Enforces:**
- Required fields & types
- Platform compatibility
- Security constraints
- Build determinism
- Execution modes

---

### 3. Security Assessment (`core/security/trust_model.py`)

**Multi-factor trust scoring**

```python
from altstore.core.security.trust_model import SecurityManager

security_mgr = SecurityManager()

# Assess application
assessment = security_mgr.assess_application(
    manifest,
    reproducibility_level="R2",        # From build verification
    malware_result="safe",             # From dry-run sandbox
    community_score=0.8,               # User votes
    github_signals={...}               # Age, stars, contributors
)

print(assessment["trust_score"])      # 0.0-1.0
print(assessment["security_policy"])  # Recommended sandbox level
```

**Factors:**
- Reproducibility (R0-R3): 0.4x score
- Malware detection: 0.3x score
- Community signals: 0.2x score
- Publish metadata: 0.1x score

**Output:** Recommended security policy (permissions, sandbox level)

---

### 4. Reproducible Builds (`core/security/reproducible_builds.py`)

**Deterministic builds → cryptographic proof of integrity**

```python
from altstore.core.security.reproducible_builds import ReproducibilityEngine

engine = ReproducibilityEngine()

# Build twice in clean Docker containers
result = engine.build_reproducibly(
    repo_path="/path/to/repo",
    build_strategy="docker",
    base_image="python:3.11@sha256:abc...",
    environment={
        "SOURCE_DATE_EPOCH": "1700000000",
        "TZ": "UTC"
    }
)

print(result.reproducibility_level)  # R0, R1, R2, or R3
print(result.hash)                   # Artifact SHA256
print(result.recipe_hash)            # Build recipe SHA256
```

**Reproducibility Levels:**
- **R0**: Not reproducible (mutable dependencies)
- **R1**: Deterministic inputs (locked versions)
- **R2**: Bit-for-bit identical builds (verifiable)
- **R3**: Signed by maintainer (highest trust)

---

### 5. WASM Fallback (`executor/wasm.py`)

**Last-resort safe execution for any app**

```python
from altstore.executor.wasm import WASMFallbackManager

wasm_mgr = WASMFallbackManager()

# Check compatibility
compat_score = wasm_mgr.compatibility_checker.check_compatibility(manifest)
# Returns 0.0-1.0 based on language, build system, permissions

# Should use WASM?
if wasm_mgr.should_use_wasm_fallback(manifest, native_success=False):
    # Prepare WASM execution
    wasm_file, config = wasm_mgr.prepare_wasm_execution(repo_path)
    
    # Execute
    success, stdout, stderr, exit_code = wasm_mgr.execute_wasm_fallback(
        wasm_file,
        config,
        args=["--help"]
    )
```

**Supported Languages:**
- Rust → wasm32-unknown-unknown (90% compatible)
- C/C++ → Emscripten (70% compatible)
- Go → TinyGo (50% compatible)
- Python → Pyodide (30% compatible)

**Fallback Reasons:**
- Native build failed
- Missing architecture support
- Offline environment
- User preference
- Security sandbox required

---

### 6. Offline Capsules (`executor/offline_orchestrator.py`)

**Self-contained, signed app packages for air-gapped environments**

```python
from altstore.executor.offline_orchestrator import (
    OfflineCapsuleBuilder, OfflineInstallationManager
)

# Build capsule (while online)
builder = OfflineCapsuleBuilder("./storage")
capsule_path = builder.build_offline_capsule(
    app_id="com.example.app",
    version="1.0.0",
    manifest=manifest_dict,
    native_artifacts=[("app_binary", binary_content)],
    wasm_artifact=wasm_binary,  # Optional fallback
    trust_snapshot=snapshot,
    platform="linux"
)

# Install capsule (completely offline)
installer = OfflineInstallationManager("./storage")
result = installer.install_from_capsule(
    capsule_path,
    allow_wasm_fallback=True
)

# Run app (offline)
trace = installer.run_app("com.example.app", "1.0.0", ["--help"])
print(trace.execution_mode)  # NATIVE or WASM
```

**Capsule Contents:**
```
capsule.tar.gz
├── native/               # Native binaries
├── wasm/                 # WASM fallback
├── metadata/
│   ├── manifest.json     # App manifest
│   ├── capsule.json      # Capsule metadata
│   ├── checksums.json    # Integrity verification
│   └── trust_snapshot.json  # Offline trust data
```

**No Network Required:**
- Install from local file/USB
- Execute with cached trust data
- Auto-select native or WASM
- Verify signatures offline

---

### 7. Frontend UI (`client/frontend.py`)

**Beautiful, non-technical user interface**

```python
from altstore.client.frontend import MainUI, AppCard, TrustLevel

# Create UI
ui = MainUI()

# Add featured apps
ui.catalog.add_featured_app(AppCard(
    app_id="com.ripgrep.ripgrep",
    name="ripgrep",
    description="Fast line search",
    publisher="BurntSushi",
    trust_level=TrustLevel.VERIFIED,
    stars=50000,
    tags=["CLI", "Rust"]
))

# Generate HTML
ui.generate_html_file("index.html")
```

**Features:**
- GitHub project explorer (live search)
- App catalog with cards
- One-click install button
- Installation progress display
- Trust indicators (verified/reproducible/unverified)
- Offline status indication
- Installation history

---

### 8. Central Orchestrator (`core/orchestrator.py`)

**Coordinates all subsystems end-to-end**

```python
from altstore.core.orchestrator import PlatformOrchestrator

orchestrator = PlatformOrchestrator("./storage", github_token="...")

# Complete workflow: GitHub → Installed App
result = await orchestrator.discover_and_install(
    "BurntSushi/ripgrep",
    user_preferences={"allow_wasm": True}
)

if result["success"]:
    print(f"Installed to: {result['install_result']['install_path']}")
    print(f"Trust score: {result['security']['trust_score']}")
```

**Workflow Stages:**
1. **Discovery**: Analyze GitHub repo
2. **Validation**: Verify manifest
3. **Build**: Reproducible build
4. **Security**: Risk assessment
5. **WASM Prep**: Fallback compatibility
6. **Capsule**: Create offline package
7. **Install**: Extract & verify
8. **Execute**: Run with fallbacks

---

## Usage Scenarios

### Scenario 1: Install from GitHub (Online)

```python
# User searches for "ripgrep" in GitHub Explorer UI
# → Finds BurntSushi/ripgrep
# → Clicks "Install"
# → System:
#   1. Analyzes repo
#   2. Generates manifest
#   3. Builds reproducibly
#   4. Creates WASM fallback
#   5. Builds offline capsule
#   6. Installs to local directory
# → User sees progress, then "Ready to Run"
```

### Scenario 2: Air-Gapped Installation

```python
# On connected machine:
capsule_path = builder.build_offline_capsule(...)
# Save to USB: cp capsule.cap /mnt/usb/

# On air-gapped machine:
installer.install_from_capsule("/mnt/usb/capsule.cap")
installer.run_app("app_id", args=[...])
# Fully works without network
```

### Scenario 3: WASM Fallback

```python
# Native build fails due to missing dependencies
# → System detects WASM compatibility (0.7)
# → Prompts user: "Run in WASM sandbox instead?"
# → Builds Rust→WASM or C→Emscripten
# → Creates WASM capsule
# → Executes via wasmtime/wasmer
# → User doesn't know difference
```

### Scenario 4: Security Review

```python
# Before installation:
analysis = await explorer.analyze_repo("new/repo")

if analysis.risk_score > 0.5:
    print("⚠️  This repository has safety concerns")
    print(f"  Reason: {analysis.repo_type}")
    print(f"  Trust: {analysis.trust_level}")
    print(f"  Sandbox: Strict (no network, read-only FS)")
    
    # User can still install with restrictions
```

---

## Key Design Decisions

### 1. **Universal Manifest**
- Single definition for all platforms
- Formally verifiable constraints
- Zero platform assumptions

### 2. **Reproducibility as Trust**
- Build twice → identical hash
- Bit-for-bit = cryptographic proof
- Better than signatures alone

### 3. **WASM as Safety Net**
- Any app → WASM when native fails
- No terminal, no privilege escalation
- Offline-compatible

### 4. **Offline-First**
- Capsules are self-contained
- No runtime network required
- Trust snapshots for verification

### 5. **No Gatekeeping**
- Anyone can publish via GitHub
- Automated scoring, not approval
- User controls trust level

---

## Data Flow Examples

### GitHub → Installed App (Complete)

```
ripgrep GitHub Repo
  ↓ (GitHubExplorer)
README analysis → Rust CLI detected
  ↓ (ManifestValidator)
Generate & validate manifest
  ↓ (SecurityManager)
Trust score: 0.92 (verified publisher)
  ↓ (ReproducibilityEngine)
Build in Docker twice → R2 (bit-for-bit)
  ↓ (WASMFallbackManager)
Rust → wasm32-unknown-unknown (compat: 0.9)
  ↓ (OfflineCapsuleBuilder)
Create .cap with native + WASM + trust snapshot
  ↓ (OfflineInstallationManager)
Extract & verify checksums
  ↓ (Launcher)
Execute native binary
  ↓
ripgrep running, can search files
```

### Offline Installation

```
capsule.cap on USB drive
  ↓ (OfflineInstallationManager)
Verify capsule signature (offline)
  ↓
Extract native artifacts
  ↓ (TrustSnapshotManager)
Check if app is revoked (cached data)
  ↓
Check trust score (cached)
  ↓ (Launcher)
Execute native binary
  ↓
App runs fully offline, no network needed
```

### WASM Fallback Chain

```
User: "Run my app"
  ↓
Try: Native binary
  ↓ (fails: libssl.so not found)
Try: WASM fallback
  ↓ (if available in capsule)
Execute via wasmtime
  ↓ (still fails: FS access denied)
Offer: Manual WASM execution with -dir flag
  ↓
User decides: run or skip
```

---

## Integration Checklist

- [x] GitHub Explorer (async API integration)
- [x] Manifest schema & validation
- [x] Formal verification (Z3/SMT constraints)
- [x] Security assessment & trust scoring
- [x] Reproducible builds (Docker-based)
- [x] WASM compatibility & builders
- [x] Offline capsules (CAS + signatures)
- [x] Installation manager (zero-network)
- [x] Frontend UI (design-focused)
- [x] Central orchestrator
- [ ] Test coverage
- [ ] API server (REST/GraphQL)
- [ ] Federation protocol (indexes)
- [ ] Desktop app wrapper (Tauri)
- [ ] Mobile app (iOS/Android)

---

## Next Steps

1. **Complete test coverage** for all modules
2. **API server** for remote operations
3. **Desktop app** wrapper (Tauri for native UI)
4. **Federation protocol** for peer indexes
5. **Economic incentives** (staking, reputation)
6. **Formal verification** improvements (full Z3)
7. **GPU-safe WASM** execution
8. **Binary transparency logs** (Sigstore)

---

## References

- Scouts.md: Comprehensive design document
- Manifest schema: appstore.dev/v1
- WASM specs: WebAssembly System Interface (WASI)
- Reproducible builds: https://reproducible-builds.org
- Z3 SMT solver: https://github.com/Z3Prover/z3
