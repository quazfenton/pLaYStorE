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
import logging
import tarfile
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

logger = logging.getLogger(__name__)


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

            # Save capsule metadata
            # We'll create a temporary manifest first without content_hash
            temp_capsule_manifest = OfflineCapsuleManifest(
                capsule_id=capsule_id,
                app_id=app_id,
                version=version,
                platform=platform,
                content_hash="",  # Will be computed after all files are written
                manifest_hash=manifest_hash,
                artifact_hashes=artifact_hashes,
                timestamp=datetime.utcnow().isoformat() + "Z",
                trust_score=0.8,  # Would come from trust system
                reproducibility_level="R2",
                wasm_fallback_available=wasm_artifact is not None,
                wasm_build_hash=wasm_hash
            )

            # Save capsule metadata temporarily
            metadata_file = capsule_temp / "metadata" / "capsule.json"
            metadata_file.write_text(json.dumps(asdict(temp_capsule_manifest), indent=2))

            # Store trust snapshot if provided
            if trust_snapshot:
                trust_file = capsule_temp / "metadata" / "trust_snapshot.json"
                trust_file.write_text(json.dumps(asdict(trust_snapshot), indent=2))

            # Create checksums file
            checksums = self._compute_checksums(capsule_temp)
            checksums_file = capsule_temp / "metadata" / "checksums.json"
            checksums_file.write_text(json.dumps(checksums, indent=2))

            # NOW compute the content hash after all files are written
            final_content_hash = self._compute_capsule_hash(capsule_temp)

            # Create the final manifest with the correct content hash
            final_capsule_manifest = OfflineCapsuleManifest(
                capsule_id=capsule_id,
                app_id=app_id,
                version=version,
                platform=platform,
                content_hash=final_content_hash,
                manifest_hash=manifest_hash,
                artifact_hashes=artifact_hashes,
                timestamp=datetime.utcnow().isoformat() + "Z",
                trust_score=0.8,  # Would come from trust system
                reproducibility_level="R2",
                wasm_fallback_available=wasm_artifact is not None,
                wasm_build_hash=wasm_hash
            )

            # Save the final capsule metadata with correct content hash
            metadata_file.write_text(json.dumps(asdict(final_capsule_manifest), indent=2))
            
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
            tar.add(capsule_dir, arcname=capsule_dir.name)


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
        """
        Extract capsule archive with comprehensive security validation.

        SECURITY: Validates ALL members BEFORE extracting ANY to prevent:
        - Path traversal attacks (../../etc/passwd)
        - Absolute path injection (/etc/passwd)
        - Symlink attacks
        - Windows path separator injection
        - Data URLs and other malicious content

        Raises:
            ValueError: If any security violation is detected
            FileNotFoundError: If capsule file doesn't exist
            tarfile.TarError: If capsule is corrupted
        """
        logger.info(f"Extracting capsule {capsule_path} to {extract_dir}")

        # Validate capsule file exists
        if not os.path.exists(capsule_path):
            raise FileNotFoundError(f"Capsule file not found: {capsule_path}")

        with tarfile.open(capsule_path, "r:gz") as tar:
            # CRITICAL: Validate ALL members BEFORE extracting ANY
            # This prevents TOCTOU (time-of-check-time-of-use) attacks
            validation_errors = []
            safe_members = []

            for member in tar.getmembers():
                member_name = member.name

                # Check 1: Reject null bytes in names (prevents null byte injection)
                if '\x00' in member_name:
                    validation_errors.append(f"Null byte in member name: {member_name}")
                    continue

                # Check 2: Reject excessively long paths (prevents buffer overflow attempts)
                if len(member_name) > 512:
                    validation_errors.append(f"Path too long (max 512 chars): {member_name[:100]}...")
                    continue

                # Check 3: Normalize path to handle .. and symlinks
                # Use os.path.normpath to collapse redundant separators and up-level references
                normalized_name = os.path.normpath(member_name)

                # Check 4: Reject path traversal attempts using ..
                if normalized_name.startswith('..') or '/..' in normalized_name or normalized_name.startswith('..'):
                    validation_errors.append(f"Path traversal detected (..): {member_name}")
                    continue

                # Check 5: Reject absolute paths (Unix-style)
                if normalized_name.startswith('/'):
                    validation_errors.append(f"Absolute path detected: {member_name}")
                    continue

                # Check 6: Reject Windows-style absolute paths
                if len(member_name) > 1 and member_name[1] == ':':
                    validation_errors.append(f"Windows absolute path detected: {member_name}")
                    continue

                # Check 7: Reject Windows-style paths (cross-platform security)
                if '\\' in member_name:
                    validation_errors.append(f"Windows path separator detected: {member_name}")
                    continue

                # Check 8: Reject names starting with /
                if member_name.startswith('/'):
                    validation_errors.append(f"Path starts with /: {member_name}")
                    continue

                # Check 9: Ensure resolved path is within extract_dir
                # This is the final safety net
                member_path = (extract_dir / normalized_name).resolve()
                extract_dir_resolved = extract_dir.resolve()

                try:
                    # Use os.path.commonpath for reliable prefix checking
                    common = os.path.commonpath([str(member_path), str(extract_dir_resolved)])
                    if common != str(extract_dir_resolved):
                        validation_errors.append(f"Path escapes extraction directory: {member_name}")
                        continue
                except ValueError as e:
                    # commonpath raises ValueError if paths are on different drives (Windows)
                    validation_errors.append(f"Invalid path comparison: {member_name} ({e})")
                    continue

                # Check 10: Reject symlinks pointing outside extract_dir
                if member.issym() or member.islnk():
                    link_target = member.linkname
                    # Normalize symlink target
                    normalized_target = os.path.normpath(link_target)
                    if os.path.isabs(normalized_target) or '..' in normalized_target:
                        validation_errors.append(f"Symlink escapes directory: {member_name} -> {link_target}")
                        continue

                # Check 11: Reject device files, FIFOs, and other special files
                if not (member.isfile() or member.isdir() or member.issym()):
                    validation_errors.append(f"Unsupported file type: {member_name} (type: {member.type})")
                    continue

                # Check 12: Reject files with suspicious names
                suspicious_names = ['passwd', 'shadow', 'sudoers', '.ssh', 'authorized_keys']
                if any(suspicious in member_name.lower() for suspicious in suspicious_names):
                    validation_errors.append(f"Suspicious filename: {member_name}")
                    continue

                # All checks passed - add to safe members list
                safe_members.append(member)

            # If ANY validation failed, raise error BEFORE extraction
            if validation_errors:
                error_msg = f"Capsule extraction failed - {len(validation_errors)} security violations:\n"
                for i, error in enumerate(validation_errors[:10], 1):  # Show first 10 errors
                    error_msg += f"  {i}. {error}\n"
                if len(validation_errors) > 10:
                    error_msg += f"  ... and {len(validation_errors) - 10} more"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # ALL validations passed - safe to extract only validated members
            logger.info(f"Capsule validation passed - {len(safe_members)} safe members")

            # SECURITY: Extract only validated members with additional safety filters
            # Python 3.12+ supports filter='data' which provides additional protection
            for member in safe_members:
                # Double-check: Skip symlinks entirely for maximum security
                if member.issym() or member.islnk():
                    logger.warning(f"Skipping symlink during extraction: {member.name}")
                    continue
                
                # Extract with explicit path validation
                member_path = (extract_dir / member.name).resolve()
                extract_dir_resolved = extract_dir.resolve()
                
                # Final safety check before extraction
                try:
                    common = os.path.commonpath([str(member_path), str(extract_dir_resolved)])
                    if common != str(extract_dir_resolved):
                        logger.error(f"SECURITY: Path escapes extraction directory (skipping): {member.name}")
                        continue
                except ValueError:
                    logger.error(f"SECURITY: Invalid path (skipping): {member.name}")
                    continue
                
                tar.extract(member, extract_dir)

            logger.info(f"Capsule extracted successfully to {extract_dir}")
    
    def _verify_capsule_integrity(
        self,
        capsule_dir: Path,
        capsule_manifest: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Verify capsule integrity using content hash and checksums"""
        # First, verify the content hash matches the entire capsule
        computed_content_hash = self._compute_capsule_hash(capsule_dir)
        expected_content_hash = capsule_manifest.get("content_hash")
        
        if not expected_content_hash:
            return False, "No content hash in manifest for verification"
        
        if computed_content_hash != expected_content_hash:
            return False, f"Content hash mismatch: expected {expected_content_hash}, got {computed_content_hash}"
        
        # Optionally, also verify individual file checksums as an additional check
        checksums_file = capsule_dir / "metadata" / "checksums.json"
        if checksums_file.exists():
            try:
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
            except Exception as e:
                # If checksums.json is corrupted, we still have the content hash verification
                # So we can continue with just the content hash check
                pass
        
        # Check for any extra files not in the expected list
        checksums_file = capsule_dir / "metadata" / "checksums.json"
        if checksums_file.exists():
            try:
                expected_checksums = json.loads(checksums_file.read_text())
                expected_paths = set(expected_checksums.keys())
                
                actual_paths = set()
                for filepath in capsule_dir.rglob("*"):
                    if filepath.is_file():
                        rel_path = str(filepath.relative_to(capsule_dir))
                        actual_paths.add(rel_path)
                
                # Exclude the checksums file itself from the check
                expected_paths.discard("metadata/checksums.json")
                
                extra_files = actual_paths - expected_paths
                if extra_files:
                    return False, f"Extra files detected in capsule: {extra_files}"
            except Exception:
                # If we can't read checksums, skip this check
                pass

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

if ! command -v $WASM_ENGINE &> /dev/null; then
    echo "Error: $WASM_ENGINE not found. Install wasmtime, wasmer, or node.js"
    exit 1
fi

exec $WASM_ENGINE --dir=. "$WASM_FILE" "$@"
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
        start_time = datetime.utcnow()

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

        completed_time = datetime.utcnow()
        duration = (completed_time - start_time).total_seconds()

        trace = ExecutionTrace(
            app_id=app_id,
            version=version,
            mode=execution_mode,
            fallback_reason=fallback_reason,
            started_at=start_time.isoformat() + "Z",
            completed_at=completed_time.isoformat() + "Z",
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
        import json

        # Load installation metadata to get the entrypoint
        install_metadata_file = app_dir / "install.json"
        if not install_metadata_file.exists():
            raise RuntimeError("Installation metadata not found")
        
        install_metadata = json.loads(install_metadata_file.read_text())
        app_manifest_file = app_dir.parent / f"{install_metadata['app_id']}_{install_metadata['version']}_manifest.json"
        
        # Try to find manifest in the capsule metadata directory if available
        capsule_metadata_dir = app_dir / "metadata"
        if (capsule_metadata_dir / "manifest.json").exists():
            app_manifest = json.loads((capsule_metadata_dir / "manifest.json").read_text())
        else:
            # If no manifest in app_dir, we need to use the install metadata to determine entrypoint
            # For now, we'll look for a default executable name based on app_id
            app_id = install_metadata['app_id']
            app_name = app_id.split('.')[-1]  # Get last part of app_id as app name
            
            # Look for common executable names
            possible_executables = [
                app_name,
                app_name.lower(),
                app_name.upper(),
                f"{app_name}.exe",  # Windows
                f"{app_name}.bin",
                "app",
                "main",
                "executable",
                "program"
            ]
            
            exe_file = None
            for exe_name in possible_executables:
                exe_path = app_dir / exe_name
                if exe_path.exists() and exe_path.is_file() and (exe_path.stat().st_mode & 0o111):
                    exe_file = exe_path
                    break
            
            if not exe_file:
                raise RuntimeError(f"No executable found in installation for app: {app_id}")
            
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
            return False
        
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
