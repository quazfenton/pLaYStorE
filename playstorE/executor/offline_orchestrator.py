"""
Offline-First Application Orchestrator for AltStore.

Manages the complete lifecycle of applications in offline/air-gapped environments:
- Capsule preparation and distribution
- WASM fallback triggering and execution
- Trust snapshot management
- Automatic fallback chains

This enables installation and execution with zero network access,
making AltStore viable for restricted environments (air-gapped, field work, offline-first).
"""

import os
import json
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil


class ExecutionMode(Enum):
    """Application execution modes"""
    NATIVE = "native"
    SANDBOX = "sandbox"
    CONTAINER = "container"
    WASM = "wasm"
    OFFLINE = "offline"


class FallbackReason(Enum):
    """Reasons for falling back to WASM"""
    NATIVE_FAILED = "native_failed"
    SANDBOX_RESTRICTED = "sandbox_restricted"
    INCOMPATIBLE_ARCH = "incompatible_arch"
    MISSING_DEPENDENCIES = "missing_dependencies"
    USER_PREFERENCE = "user_preference"
    OFFLINE_ONLY = "offline_only"


@dataclass
class ExecutionTrace:
    """Trace of an application execution"""
    app_id: str
    version: str
    mode: ExecutionMode
    fallback_reason: Optional[FallbackReason]
    started_at: str
    completed_at: Optional[str]
    exit_code: Optional[int]
    stdout: str
    stderr: str
    duration_seconds: Optional[float]


@dataclass
class TrustSnapshot:
    """Immutable snapshot of trust data for offline use"""
    snapshot_id: str
    timestamp: str
    as_of_date: str
    trusted_publishers: List[str]
    revoked_apps: List[str]
    risk_scores: Dict[str, float]
    reproducibility_levels: Dict[str, str]
    signature: Optional[str] = None


@dataclass
class OfflineCapsuleManifest:
    """Extended manifest for offline capsule with fallback info"""
    capsule_id: str
    app_id: str
    version: str
    platform: str
    content_hash: str
    manifest_hash: str
    artifact_hashes: List[str]
    timestamp: str
    trust_score: float
    reproducibility_level: str
    wasm_fallback_available: bool
    wasm_build_hash: Optional[str] = None
    dependencies: List[str] = None


class OfflineCapsuleBuilder:
    """
    Builds self-contained capsules for offline distribution.
    
    Includes:
    - Native artifacts
    - WASM fallback build
    - Trust snapshots
    - Dependency information
    - Deterministic build metadata
    """
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.capsules_dir = self.storage_path / "capsules"
        self.wasm_dir = self.storage_path / "wasm"
        self.capsules_dir.mkdir(parents=True, exist_ok=True)
        self.wasm_dir.mkdir(parents=True, exist_ok=True)
    
    def build_offline_capsule(
        self,
        app_id: str,
        version: str,
        manifest: Dict[str, Any],
        native_artifacts: List[Tuple[str, bytes]],
        wasm_artifact: Optional[bytes] = None,
        trust_snapshot: Optional[TrustSnapshot] = None,
        platform: str = "universal"
    ) -> str:
        """
        Build a complete offline capsule with fallback support.
        
        Args:
            app_id: Application ID
            version: Application version
            manifest: Application manifest (dict)
            native_artifacts: List of (filename, content) tuples
            wasm_artifact: Optional WASM binary
            trust_snapshot: Optional trust data snapshot
            platform: Target platform
        
        Returns:
            Path to created capsule file
        """
        capsule_id = f"cap_{app_id}_{version}_{platform}_{int(datetime.now().timestamp())}"
        capsule_path = self.capsules_dir / f"{capsule_id}.capsule"
        
        # Create capsule directory
        capsule_temp = Path(tempfile.mkdtemp(prefix="capsule_"))
        
        try:
            # Create directory structure
            (capsule_temp / "native").mkdir(exist_ok=True)
            (capsule_temp / "wasm").mkdir(exist_ok=True)
            (capsule_temp / "metadata").mkdir(exist_ok=True)
            
            # Store native artifacts
            artifact_hashes = []
            for filename, content in native_artifacts:
                artifact_path = capsule_temp / "native" / filename
                artifact_path.write_bytes(content)
                artifact_hash = hashlib.sha256(content).hexdigest()
                artifact_hashes.append(artifact_hash)
            
            # Store WASM fallback if available
            wasm_hash = None
            if wasm_artifact:
                wasm_path = capsule_temp / "wasm" / "app.wasm"
                wasm_path.write_bytes(wasm_artifact)
                wasm_hash = hashlib.sha256(wasm_artifact).hexdigest()
            
            # Store manifest
            manifest_path = capsule_temp / "metadata" / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))
            manifest_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
            
            # Create capsule metadata
            capsule_manifest = OfflineCapsuleManifest(
                capsule_id=capsule_id,
                app_id=app_id,
                version=version,
                platform=platform,
                content_hash=self._compute_capsule_hash(capsule_temp),
                manifest_hash=manifest_hash,
                artifact_hashes=artifact_hashes,
                timestamp=datetime.utcnow().isoformat() + "Z",
                trust_score=0.8,  # Would come from trust system
                reproducibility_level="R2",
                wasm_fallback_available=wasm_artifact is not None,
                wasm_build_hash=wasm_hash
            )
            
            # Save capsule metadata
            metadata_file = capsule_temp / "metadata" / "capsule.json"
            metadata_file.write_text(json.dumps(asdict(capsule_manifest), indent=2))
            
            # Store trust snapshot if provided
            if trust_snapshot:
                trust_file = capsule_temp / "metadata" / "trust_snapshot.json"
                trust_file.write_text(json.dumps(asdict(trust_snapshot), indent=2))
            
            # Create checksums file
            checksums = self._compute_checksums(capsule_temp)
            checksums_file = capsule_temp / "metadata" / "checksums.json"
            checksums_file.write_text(json.dumps(checksums, indent=2))
            
            # Create tarball capsule
            self._create_capsule_archive(capsule_temp, capsule_path)
            
            return str(capsule_path)
        
        finally:
            # Clean up temporary directory
            shutil.rmtree(capsule_temp, ignore_errors=True)
    
    def _compute_capsule_hash(self, capsule_dir: Path) -> str:
        """Compute deterministic hash of capsule contents"""
        hasher = hashlib.sha256()
        
        # Hash files in deterministic order
        for filepath in sorted(capsule_dir.rglob("*")):
            if filepath.is_file():
                with open(filepath, "rb") as f:
                    hasher.update(f.read())
        
        return hasher.hexdigest()
    
    def _compute_checksums(self, capsule_dir: Path) -> Dict[str, str]:
        """Compute checksums for all files in capsule"""
        checksums = {}
        
        for filepath in capsule_dir.rglob("*"):
            if filepath.is_file():
                rel_path = filepath.relative_to(capsule_dir)
                with open(filepath, "rb") as f:
                    checksums[str(rel_path)] = hashlib.sha256(f.read()).hexdigest()
        
        return checksums
    
    def _create_capsule_archive(self, capsule_dir: Path, output_path: Path):
        """Create compressed capsule archive"""
        import tarfile
        
        with tarfile.open(output_path, "w:gz") as tar:
            for item in capsule_dir.iterdir():
                tar.add(item, arcname=item.name)


class OfflineInstallationManager:
    """
    Manages installation of applications in offline environments.
    
    Handles:
    - Capsule verification
    - Fallback chain selection
    - Trust snapshot application
    - Dependency resolution (offline)
    """
    
    def __init__(self, storage_path: str, wasm_executor=None):
        self.storage_path = Path(storage_path)
        self.install_dir = self.storage_path / "installed"
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.wasm_executor = wasm_executor
        self.execution_traces: List[ExecutionTrace] = []
    
    def install_from_capsule(
        self,
        capsule_path: str,
        trust_data: Optional[Dict[str, Any]] = None,
        allow_wasm_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Install an application from an offline capsule.
        
        Args:
            capsule_path: Path to capsule file
            trust_data: Optional local trust data
            allow_wasm_fallback: Whether to use WASM fallback if needed
        
        Returns:
            Installation result
        """
        try:
            # Extract and verify capsule
            capsule_dir = Path(tempfile.mkdtemp(prefix="capsule_extract_"))
            self._extract_capsule(capsule_path, capsule_dir)
            
            # Load capsule metadata
            metadata_file = capsule_dir / "metadata" / "capsule.json"
            capsule_manifest = json.loads(metadata_file.read_text())
            
            # Verify integrity
            is_valid, error = self._verify_capsule_integrity(capsule_dir, capsule_manifest)
            if not is_valid:
                return {"success": False, "error": error}
            
            # Load application manifest
            app_manifest_file = capsule_dir / "metadata" / "manifest.json"
            app_manifest = json.loads(app_manifest_file.read_text())
            
            # Create installation directory
            app_id = capsule_manifest["app_id"]
            version = capsule_manifest["version"]
            app_install_dir = self.install_dir / f"{app_id}_{version}"
            app_install_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine execution mode
            execution_mode = self._select_execution_mode(
                capsule_manifest,
                app_manifest,
                allow_wasm_fallback
            )
            
            # Install artifacts based on mode
            if execution_mode == ExecutionMode.NATIVE:
                self._install_native_artifacts(capsule_dir, app_install_dir)
                fallback_reason = None
            
            elif execution_mode == ExecutionMode.WASM:
                if not capsule_manifest.get("wasm_fallback_available"):
                    return {
                        "success": False,
                        "error": "Native execution unavailable and WASM fallback not available"
                    }
                
                self._install_wasm_artifacts(capsule_dir, app_install_dir)
                fallback_reason = FallbackReason.NATIVE_FAILED
            
            else:
                return {
                    "success": False,
                    "error": f"Execution mode {execution_mode} not supported in offline mode"
                }
            
            # Save installation metadata
            install_metadata = {
                "capsule_id": capsule_manifest["capsule_id"],
                "app_id": app_id,
                "version": version,
                "installed_at": datetime.utcnow().isoformat() + "Z",
                "execution_mode": execution_mode.value,
                "fallback_reason": fallback_reason.value if fallback_reason else None,
                "trust_score": capsule_manifest.get("trust_score"),
                "reproducibility_level": capsule_manifest.get("reproducibility_level")
            }
            
            install_metadata_file = app_install_dir / "install.json"
            install_metadata_file.write_text(json.dumps(install_metadata, indent=2))
            
            # Cleanup
            shutil.rmtree(capsule_dir, ignore_errors=True)
            
            return {
                "success": True,
                "app_id": app_id,
                "version": version,
                "install_path": str(app_install_dir),
                "execution_mode": execution_mode.value,
                "manifest": app_manifest
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _extract_capsule(self, capsule_path: str, extract_dir: Path):
        """Extract capsule archive"""
        import tarfile
        
        with tarfile.open(capsule_path, "r:gz") as tar:
            tar.extractall(extract_dir)
    
    def _verify_capsule_integrity(
        self,
        capsule_dir: Path,
        capsule_manifest: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Verify capsule integrity using checksums"""
        checksums_file = capsule_dir / "metadata" / "checksums.json"
        expected_checksums = json.loads(checksums_file.read_text())
        
        # Verify each file
        for rel_path, expected_hash in expected_checksums.items():
            filepath = capsule_dir / rel_path
            if not filepath.exists():
                return False, f"Missing file: {rel_path}"
            
            # Skip checksum files themselves
            if rel_path.endswith("checksums.json"):
                continue
            
            with open(filepath, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()
            
            if actual_hash != expected_hash:
                return False, f"Checksum mismatch for {rel_path}"
        
        return True, None
    
    def _select_execution_mode(
        self,
        capsule_manifest: Dict[str, Any],
        app_manifest: Dict[str, Any],
        allow_wasm_fallback: bool
    ) -> ExecutionMode:
        """Select appropriate execution mode"""
        # Prefer native when available
        native_artifacts = capsule_manifest.get("artifact_hashes", [])
        if native_artifacts:
            return ExecutionMode.NATIVE
        
        # Fall back to WASM if available
        if allow_wasm_fallback and capsule_manifest.get("wasm_fallback_available"):
            return ExecutionMode.WASM
        
        # Last resort: offline mode (manual execution)
        return ExecutionMode.OFFLINE
    
    def _install_native_artifacts(self, capsule_dir: Path, install_dir: Path):
        """Install native artifacts"""
        native_dir = capsule_dir / "native"
        if native_dir.exists():
            for artifact_file in native_dir.iterdir():
                shutil.copy2(artifact_file, install_dir / artifact_file.name)
    
    def _install_wasm_artifacts(self, capsule_dir: Path, install_dir: Path):
        """Install WASM artifacts and configuration"""
        wasm_dir = capsule_dir / "wasm"
        if wasm_dir.exists():
            for wasm_file in wasm_dir.iterdir():
                shutil.copy2(wasm_file, install_dir / wasm_file.name)
        
        # Create WASM run script
        wasm_run_script = install_dir / "run_wasm.sh"
        wasm_run_script.write_text("""#!/bin/bash
# WASM Fallback Launcher
# Runs application in WASM sandbox

WASM_FILE="app.wasm"
WASM_ENGINE="${WASM_ENGINE:-wasmtime}"

if ! command -v "$WASM_ENGINE" &> /dev/null; then
    echo "Error: $WASM_ENGINE not found. Install wasmtime, wasmer, or node.js"
    exit 1
fi

exec "$WASM_ENGINE" --dir=. "$WASM_FILE" "$@"
""")
        wasm_run_script.chmod(0o755)
    
    def run_app(
        self,
        app_id: str,
        version: str,
        args: List[str] = None
    ) -> ExecutionTrace:
        """
        Run an installed application.
        
        Returns execution trace for debugging and auditing.
        """
        import subprocess
        from datetime import datetime
        
        app_install_dir = self.install_dir / f"{app_id}_{version}"
        
        if not app_install_dir.exists():
            raise RuntimeError(f"Application not found: {app_id} v{version}")
        
        # Load installation metadata
        install_metadata_file = app_install_dir / "install.json"
        install_metadata = json.loads(install_metadata_file.read_text())
        
        execution_mode = ExecutionMode(install_metadata["execution_mode"])
        fallback_reason = None
        if install_metadata.get("fallback_reason"):
            fallback_reason = FallbackReason(install_metadata["fallback_reason"])
        
        # Execute based on mode
        start_time = datetime.now()
        
        try:
            if execution_mode == ExecutionMode.NATIVE:
                result = self._run_native(app_install_dir, args or [])
            elif execution_mode == ExecutionMode.WASM:
                result = self._run_wasm(app_install_dir, args or [])
            else:
                raise RuntimeError(f"Cannot auto-execute in {execution_mode} mode. Manual execution required.")
            
            stdout, stderr, exit_code = result
        
        except Exception as e:
            stdout = ""
            stderr = str(e)
            exit_code = 1
        diff
        --- a/playstorE/executor/offline_orchestrator.py
        +++ b/playstorE/executor/offline_orchestrator.py
        @@ -469,14 +469,14 @@
                     fallback_reason = FallbackReason(install_metadata["fallback_reason"])
         
                 # Execute based on mode
        -        start_time = datetime.now()
        +        start_time = datetime.utcnow()
         
                 try:
                     if execution_mode == ExecutionMode.NATIVE:
                         result = self._run_native(app_install_dir, args or [])
                     elif execution_mode == ExecutionMode.WASM:
                         result = self._run_wasm(app_install_dir, args or [])
        -            else:
        +            else: # Lines 482-485 are unchanged context
                         raise RuntimeError(f"Cannot auto-execute in {execution_mode} mode. Manual execution required.")
             
                     stdout, stderr, exit_code = result
        @@ -485,7 +485,7 @@
                     stdout = ""
                     stderr = str(e)
                     exit_code = 1
        -        
        -        duration = (datetime.now() - start_time).total_seconds()
        -        
        +        # Lines 486-494 are the target range for the original request
        +        duration = (datetime.utcnow() - start_time).total_seconds()
        +
                 trace = ExecutionTrace(
                     app_id=app_id,
                     version=version,
                     mode=execution_mode,
                     fallback_reason=fallback_reason,
                     started_at=start_time.isoformat() + "Z",
        -
            completed_at=datetime.now().isoformat() + "Z",
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration
        )
        
        self.execution_traces.append(trace)
        return trace
    
    def _run_native(self, app_dir: Path, args: List[str]) -> Tuple[str, str, int]:
        """Execute native binary"""
        import subprocess
        
        # Find executable
        exe_file = None
        for f in app_dir.iterdir():
            if f.is_file() and (f.stat().st_mode & 0o111):
                exe_file = f
                break
        
        if not exe_file:
            raise RuntimeError("No executable found in installation")
        
        result = subprocess.run(
            [str(exe_file)] + args,
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return result.stdout, result.stderr, result.returncode
    
    def _run_wasm(self, app_dir: Path, args: List[str]) -> Tuple[str, str, int]:
        """Execute WASM binary"""
        import subprocess
        
        wasm_script = app_dir / "run_wasm.sh"
        if not wasm_script.exists():
            raise RuntimeError("WASM run script not found")
        
        result = subprocess.run(
            [str(wasm_script)] + args,
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return result.stdout, result.stderr, result.returncode


class TrustSnapshotManager:
    """
    Manages trust data snapshots for offline verification.
    
    Allows users to:
    - Import trust data while online
    - Use cached trust data while offline
    - Compare against local revocation lists
    """
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.snapshots_dir = self.storage_path / "trust_snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
    
    def save_trust_snapshot(self, snapshot: TrustSnapshot) -> bool:
        """Save a trust snapshot for offline use"""
        try:
            snapshot_file = self.snapshots_dir / f"trust_{snapshot.as_of_date}.json"
            snapshot_file.write_text(json.dumps(asdict(snapshot), indent=2))
            return True
        except Exception as e:
            print(f"Failed to save trust snapshot: {e}")
            return False
    
    def get_latest_snapshot(self) -> Optional[TrustSnapshot]:
        """Get the most recent trust snapshot"""
        if not list(self.snapshots_dir.glob("trust_*.json")):
            return None
        
        latest_file = max(self.snapshots_dir.glob("trust_*.json"), key=lambda p: p.stat().st_mtime)
        data = json.loads(latest_file.read_text())
        
        return TrustSnapshot(**data)
    
    def is_app_revoked(self, app_id: str) -> bool:
        """Check if an app is revoked (offline)"""
        snapshot = self.get_latest_snapshot()
        if not snapshot:
            # Fail-closed: no trust data means we can't verify
            import warnings
            warnings.warn("No trust snapshot available — treating app as potentially revoked")
            return True

        return app_id in snapshot.revoked_apps
    
    def get_risk_score(self, app_id: str) -> Optional[float]:
        """Get offline risk score for an app"""
        snapshot = self.get_latest_snapshot()
        if not snapshot:
            return None
        
        return snapshot.risk_scores.get(app_id)


# Example usage
if __name__ == "__main__":
    # Create offline capsule
    builder = OfflineCapsuleBuilder("./offline_storage")
    
    manifest = {
        "apiVersion": "appstore.dev/v1",
        "kind": "Application",
        "metadata": {
            "app_id": "example.app",
            "name": "Example App",
            "description": "Test application"
        }
    }
    
    native_artifacts = [
        ("app_binary", b"binary content here"),
        ("config.json", json.dumps({"version": "1.0"}).encode())
    ]
    
    wasm_artifact = b"WASM binary content"
    
    capsule_path = builder.build_offline_capsule(
        app_id="example.app",
        version="1.0.0",
        manifest=manifest,
        native_artifacts=native_artifacts,
        wasm_artifact=wasm_artifact
    )
    
    print(f"Created capsule: {capsule_path}")
    
    # Install from capsule
    installer = OfflineInstallationManager("./offline_storage")
    result = installer.install_from_capsule(capsule_path)
    print(f"Installation result: {result}")
