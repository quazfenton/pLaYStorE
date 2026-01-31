# Alternative App Store Platform (AltStore) Documentation

## Overview

The Alternative App Store Platform (AltStore) is a decentralized, secure, and reproducible application distribution system that transforms GitHub repositories into one-click runnable applications. The platform emphasizes security, reproducibility, and offline-first capabilities while maintaining a familiar app store user experience.

## Architecture

### Core Components

#### 1. Manifest System
The platform uses a universal manifest format that abstracts platform and source differences:

```yaml
apiVersion: appstore.dev/v1
kind: Application

metadata:
  app_id: org.blender.blender
  name: Blender
  description: 3D creation suite
  homepage: https://blender.org
  license: GPL-3.0

publisher:
  name: Blender Foundation
  verified_domains: [blender.org]

source:
  type: github_release
  repo: blender/blender
  asset_regex: "blender-.*windows.*zip"

versions:
  strategy: semver
  auto_update: true

build:
  strategy: none  # Pre-built binary
  commands: []

run:
  type: desktop
  entrypoint: blender.exe
  args: []

security:
  sandbox: strict
  network: outbound
  filesystem: user_home
  allow_gpu: true

trust:
  verification: signed
  checksums:
    sha256: auto
```

#### 2. Security & Trust Model
- **Formal Verification**: Uses SMT/Z3 to verify manifest compliance with security policies
- **Multi-layered Sandboxing**: Implements native, container, and WASM sandboxes
- **Reproducible Builds**: Ensures bit-for-bit identical builds across environments
- **Malware Detection**: Static and dynamic analysis with behavioral telemetry

#### 3. Cross-Platform Execution
- **Native Sandboxing**: Linux (bubblewrap/seccomp), Windows (AppContainer), macOS (seatbelt)
- **Container Execution**: Docker-based builds with strict network/fs controls
- **WASM Fallback**: Secure execution for untrusted or incompatible applications
- **VM Isolation**: Optional full virtualization for maximum security

## Key Features

### GitHub Auto-Wrapping
The platform automatically detects and wraps GitHub repositories:
- Static analysis of file presence (Dockerfile, requirements.txt, package.json, etc.)
- README semantic parsing for run instructions
- Runtime intent classification (CLI, Server, Desktop, AI App)
- Build strategy selection matrix
- Dry-run sandbox for behavior observation

### Reproducible Builds
Ensures trust through deterministic builds:
- Containerized builds with pinned base images
- Deterministic environment (fixed timestamps, locales)
- Hash comparison between builds
- Reproducibility levels (R0-R3)
- Signed reproducible builds (R3)

### Offline-First Architecture
- Content Addressable Storage (CAS) for artifacts
- Installation capsules (.cap format) with signatures
- Immutable content with verifiable hashes
- Air-gapped installation support
- Local trust snapshot management

### Federated Index System
- Decentralized index synchronization
- Cryptographic signatures for integrity
- Conflict resolution mechanisms
- Peer-to-peer propagation
- Trust score aggregation

## Security Model

### Trust Levels
- 🔒 **Verified**: Signed by publisher with reproducible builds
- 🟡 **Reproducible**: Deterministic build from source
- 🔴 **Unverified**: Runs in strict sandbox only

### Sandboxing Guarantees
- **No privilege escalation**: User-mode only
- **No persistence by default**: Ephemeral filesystem
- **No network by default**: Explicit allow policy
- **Resource limits**: CPU/RAM constraints
- **Observable behavior**: Port/syscall monitoring

### Malware Detection
- Static code analysis (AST-level)
- Binary analysis and YARA rules
- Dependency graph risk assessment
- Behavioral sandbox (dry-run)
- Reputation and temporal signals

## Implementation Details

### Core Modules

#### Manifest Schema & Validation (`core/types/manifest_schema.py`)
- Strict JSON Schema validation
- Type definitions for all manifest fields
- Programmatic manifest creation and manipulation

#### Formal Verification (`core/validation/formal_verifier.py`)
- SMT/Z3-based constraint solving
- Policy validation (network requires reproducibility, etc.)
- Permission combination safety checks

#### Sandbox System (`sandbox/base.py`)
- Cross-platform sandbox abstraction
- Native, container, and WASM implementations
- Security level controls (strict/relaxed/trusted)

#### Malware Detection (`sandbox/dry_run.py`)
- Safe execution environment for behavior observation
- Port binding and network attempt detection
- Long-running process identification
- Suspicious pattern matching

#### GitHub Analyzer (`core/types/github_analyzer.py`)
- Repository structure analysis
- Language and runtime detection
- Build instruction extraction
- Archetype classification (CLI/Server/Desktop/etc.)

#### Reproducible Builds (`core/security/reproducible_builds.py`)
- Deterministic build environments
- Recipe hashing and verification
- Reproducibility level assignment
- Trust impact calculation

#### WASM Execution (`executor/wasm.py`)
- WASM compatibility checking
- Multiple engine support (Wasmtime, Wasmer, Node.js)
- Secure execution configuration
- Fallback execution paths

#### Federated Index (`storage/indexes/federated.py`)
- Cryptographic signing and verification
- Snapshot-based synchronization
- Peer-to-peer propagation
- Conflict resolution

#### Monetization System (`core/economics/monetization.py`)
- Reputation-based submission tiers
- Fee structure for unverified publishers
- Economic incentives for reproducibility
- Staking and refund mechanisms

#### Trust Model (`core/security/trust_model.py`)
- Multi-factor trust scoring
- Security policy orchestration
- Trust registry and auditing
- Revocation mechanisms

#### Capsule System (`storage/cas/capsules.py`)
- Content addressable storage
- Installation capsule format
- Integrity verification
- Offline distribution

## Usage Examples

### Creating an Application Manifest
```python
from altstore.core.types.manifest_schema import (
    AppManifest, Publisher, Source, Versions, Build, Run, 
    Security, Trust
)

manifest = AppManifest(
    api_version="appstore.dev/v1",
    kind="Application",
    metadata={
        "app_id": "com.example.myapp",
        "name": "My Application",
        "description": "A sample application"
    },
    publisher=Publisher(
        name="Example Publisher",
        verified_domains=["example.com"]
    ),
    source=Source(
        type="github_repo",
        repo="example/myapp"
    ),
    versions=Versions(strategy="semver"),
    build=Build(
        strategy="docker",
        commands=["pip install -r requirements.txt", "python setup.py build"]
    ),
    run=Run(
        type="server",
        entrypoint="app.py",
        args=["--port", "8080"]
    ),
    security=Security(
        sandbox="strict",
        network="outbound",
        filesystem="readonly",
        allow_gpu=False
    ),
    trust=Trust(verification="reproducible")
)
```

### Validating a Manifest
```python
from altstore.core.types.manifest_schema import ManifestValidator

validator = ManifestValidator()
is_valid = validator.validate(manifest.to_dict())
print(f"Manifest is valid: {is_valid}")
```

### Performing Security Assessment
```python
from altstore.core.security.trust_model import SecurityManager
from altstore.core.security.reproducible_builds import ReproducibilityLevel
from altstore.sandbox.dry_run import MalwareDetectionResult

security_manager = SecurityManager()
assessment = security_manager.assess_application(
    manifest,
    ReproducibilityLevel.R2,
    MalwareDetectionResult.SAFE,
    community_score=0.8
)
print(f"Trust score: {assessment['trust_score']}")
print(f"Security policy: {assessment['security_policy']}")
```

## Development

### Project Structure
```
altstore/
├── api/                 # API services
├── client/              # Client UI
│   ├── components/      # UI components
│   ├── views/          # View controllers
│   └── pages/          # Page layouts
├── core/               # Core business logic
│   ├── types/          # Type definitions
│   ├── validation/     # Validation logic
│   └── security/       # Security implementations
├── executor/           # Execution environments
│   ├── sandbox/        # Sandboxing
│   ├── wasm/          # WASM execution
│   └── native/        # Native execution
├── manifests/          # Manifest handling
├── storage/            # Storage implementations
│   ├── cas/           # Content addressable storage
│   └── indexes/       # Index management
├── utils/              # Utility functions
└── tests/              # Test suites
```

### Testing
Run the comprehensive test suite:
```bash
python -m altstore.tests.comprehensive_tests
```

## Deployment

### Prerequisites
- Python 3.8+
- Docker (for containerized builds)
- System dependencies for sandboxing (bubblewrap on Linux)

### Installation
```bash
pip install -r requirements.txt
```

### Configuration
The platform supports various configuration options for:
- Storage backends
- Security policies
- Network settings
- Trust thresholds

## Security Considerations

### Threat Model
- Malicious publishers
- Compromised dependencies
- Supply chain attacks
- Privilege escalation attempts
- Data exfiltration attempts

### Defense in Depth
- Multiple validation layers
- Isolation boundaries
- Least privilege execution
- Behavioral monitoring
- Automated revocation

## Future Enhancements

### Planned Features
- GPU-safe AI model execution
- Binary transparency logs
- Advanced WASM + GPU sandboxing
- Formal verification of manifests
- Federation between indexes
- Economic incentives for reproducibility

### Roadmap
1. **Phase 1**: Core functionality and security
2. **Phase 2**: Federated indexing and economics
3. **Phase 3**: Advanced execution environments
4. **Phase 4**: Formal verification and compliance

## Legal & Compliance

The platform operates as a distribution facilitator, not a host:
- No rehosting without consent
- Clear publisher opt-out mechanisms
- Transparent takedown processes
- Jurisdiction-agnostic core design
- Forkability for governance resilience

---

*This documentation reflects the implementation based on the scouts.md specification as of January 20, 2026.*