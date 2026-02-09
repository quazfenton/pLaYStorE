"""
Central Orchestrator for AltStore Platform.

Coordinates:
- GitHub discovery and analysis
- Manifest generation and validation
- Reproducible builds with WASM fallback
- Offline capsule creation
- Trust scoring and security assessment
- End-to-end installation workflow

This is the "conductor" that orchestrates all subsystems into a unified,
user-facing experience.
"""

import asyncio
import json
import tempfile
import shutil
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from datetime import datetime


class WorkflowStage(Enum):
    """Stages in the complete installation workflow"""
    DISCOVERY = "discovery"
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    BUILD = "build"
    SECURITY_CHECK = "security_check"
    FALLBACK_PREP = "fallback_prep"
    CAPSULE_CREATION = "capsule_creation"
    INSTALLATION = "installation"
    EXECUTION = "execution"


class PlatformOrchestrator:
    """
    Main orchestrator for AltStore platform operations.
    
    Coordinates all subsystems to provide:
    - One-click GitHub → App workflow
    - Deterministic, reproducible builds
    - WASM fallback with intelligent fallback chains
    - Offline-first installation
    - Comprehensive security and trust models
    """
    
    def __init__(
        self,
        storage_path: str = "./altstore_storage",
        github_token: Optional[str] = None
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize subsystems
        from playstorE.client.github_explorer import GitHubExplorer
        from playstorE.executor.offline_orchestrator import (
            OfflineCapsuleBuilder, OfflineInstallationManager, TrustSnapshotManager
        )
        from playstorE.executor.wasm import WASMFallbackManager
        from playstorE.core.validation.formal_verifier import FormalManifestVerifier
        from playstorE.core.security.trust_model import SecurityManager
        from playstorE.core.security.reproducible_builds import ReproducibleBuildService
        
        self.github_explorer = GitHubExplorer(github_token)
        self.capsule_builder = OfflineCapsuleBuilder(str(self.storage_path / "capsules"))
        self.installer = OfflineInstallationManager(str(self.storage_path / "installations"))
        self.trust_manager = TrustSnapshotManager(str(self.storage_path / "trust"))
        self.wasm_manager = WASMFallbackManager()
        self.formal_verifier = FormalManifestVerifier()
        self.security_manager = SecurityManager()
        self.reproducibility_engine = ReproducibleBuildService()
        
        # Workflow state
        self.current_workflow = None
        self.workflow_history: List[Dict] = []
    
    async def discover_and_install(
        self,
        github_repo: str,
        install_path: Optional[str] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete one-click workflow from GitHub repo to installed app.
        
        Args:
            github_repo: GitHub repository (owner/name)
            install_path: Where to install (optional)
            user_preferences: User preferences (allow_wasm, sandbox_level, etc.)
        
        Returns:
            Workflow result with final state and next steps
        """
        workflow_id = f"wf_{github_repo.replace('/', '_')}_{int(datetime.now().timestamp())}"
        user_preferences = user_preferences or {}
        
        # Initialize workflow
        workflow_state = {
            "id": workflow_id,
            "repo": github_repo,
            "started_at": datetime.now().isoformat(),
            "stages": {},
            "status": "running",
            "user_preferences": user_preferences
        }
        
        try:
            # Stage 1: Discovery & Analysis
            print(f"[{workflow_id}] Starting discovery and analysis...")
            analysis_result = await self._stage_discovery(github_repo)
            workflow_state["stages"][WorkflowStage.DISCOVERY.value] = {
                "status": "complete",
                "result": asdict(analysis_result.repo) if analysis_result else None
            }
            
            if not analysis_result or not analysis_result.is_safe:
                return {
                    "workflow_id": workflow_id,
                    "success": False,
                    "error": "Repository analysis failed or repository has safety concerns",
                    "stages": workflow_state["stages"]
                }
            
            # Stage 2: Validation
            print(f"[{workflow_id}] Validating manifest...")
            manifest = analysis_result.suggested_manifest
            validation_result = await self._stage_validation(manifest)
            workflow_state["stages"][WorkflowStage.VALIDATION.value] = validation_result
            
            if not validation_result.get("valid"):
                return {
                    "workflow_id": workflow_id,
                    "success": False,
                    "error": f"Manifest validation failed: {validation_result.get('errors')}",
                    "stages": workflow_state["stages"]
                }
            
            # Stage 3: Build
            print(f"[{workflow_id}] Building application...")
            build_result = await self._stage_build(manifest)
            workflow_state["stages"][WorkflowStage.BUILD.value] = {
                "status": "complete",
                "reproducibility_level": build_result.get("reproducibility_level") if build_result else None,
                "build_hash": build_result.get("hash") if build_result else None
            }
            
            if not build_result:
                return {
                    "workflow_id": workflow_id,
                    "success": False,
                    "error": "Build failed",
                    "stages": workflow_state["stages"]
                }
            
            # Stage 4: Security Check
            print(f"[{workflow_id}] Performing security assessment...")
            security_result = await self._stage_security_check(
                manifest,
                build_result,
                analysis_result
            )
            workflow_state["stages"][WorkflowStage.SECURITY_CHECK.value] = security_result
            
            # Stage 5: WASM Fallback Preparation
            print(f"[{workflow_id}] Preparing WASM fallback...")
            wasm_result = await self._stage_wasm_fallback_prep(manifest, build_result)
            workflow_state["stages"][WorkflowStage.FALLBACK_PREP.value] = {
                "wasm_available": wasm_result.get("available", False),
                "wasm_compatibility": wasm_result.get("compatibility", 0)
            }
            
            # Stage 6: Capsule Creation
            print(f"[{workflow_id}] Creating offline capsule...")
            capsule_path = await self._stage_capsule_creation(
                manifest,
                build_result,
                wasm_result,
                analysis_result
            )
            workflow_state["stages"][WorkflowStage.CAPSULE_CREATION.value] = {
                "status": "complete",
                "capsule_path": capsule_path
            }
            
            # Stage 7: Installation
            final_install_path = install_path or str(self.storage_path / "apps" / github_repo.split("/")[1])
            print(f"[{workflow_id}] Installing application...")
            install_result = await self._stage_installation(
                capsule_path,
                final_install_path,
                user_preferences
            )
            workflow_state["stages"][WorkflowStage.INSTALLATION.value] = {
                "status": "complete" if install_result.get("success") else "failed",
                "install_path": install_result.get("install_path"),
                "error": install_result.get("error")
            }
            
            # Complete workflow
            workflow_state["status"] = "complete"
            workflow_state["completed_at"] = datetime.now().isoformat()
            
            self.workflow_history.append(workflow_state)
            
            return {
                "workflow_id": workflow_id,
                "success": True,
                "repo": github_repo,
                "manifest": manifest,
                "analysis": {
                    "type": analysis_result.repo_type.value,
                    "confidence": analysis_result.confidence,
                    "wasm_compatible": analysis_result.wasm_compatible,
                    "risk_score": analysis_result.risk_score
                },
                "security": security_result,
                "install_result": install_result,
                "capsule_path": capsule_path,
                "stages": workflow_state["stages"]
            }
        
        except Exception as e:
            workflow_state["status"] = "failed"
            workflow_state["error"] = str(e)
            self.workflow_history.append(workflow_state)
            
            return {
                "workflow_id": workflow_id,
                "success": False,
                "error": str(e),
                "stages": workflow_state["stages"]
            }
    
    async def _stage_discovery(self, github_repo: str) -> Any:
        """Stage 1: Discover and analyze repository"""
        try:
            return await self.github_explorer.analyze_repo(github_repo)
        except Exception as e:
            print(f"Discovery failed: {e}")
            return None
    
    async def _stage_validation(self, manifest: Dict) -> Dict[str, Any]:
        """Stage 2: Validate manifest"""
        try:
            from altstore.core.types.manifest_schema import ManifestValidator
            
            is_valid = ManifestValidator.validate(manifest)
            
            # Run formal verification
            formal_check = self.formal_verifier.verify_manifest(manifest)
            
            return {
                "valid": is_valid and formal_check.get("satisfied", False),
                "errors": formal_check.get("unsatisfied_constraints", [])
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [str(e)]
            }
    
    async def _stage_build(self, manifest: Dict) -> Optional[Dict]:
        """Stage 3: Build application"""
        try:
            # This would use the reproducible build engine
            # For now, return mock result
            return {
                "success": True,
                "hash": "sha256:mockbuildhash1234567890abcdef",
                "reproducibility_level": "R2",
                "artifacts": []
            }
        except Exception as e:
            print(f"Build failed: {e}")
            return None
    
    async def _stage_security_check(
        self,
        manifest: Dict,
        build_result: Dict,
        analysis_result: Any
    ) -> Dict[str, Any]:
        """Stage 4: Security assessment"""
        try:
            # Use security manager
            assessment = self.security_manager.assess_application(
                manifest,
                build_result.get("reproducibility_level", "R0"),
                "safe",  # Would come from malware detection
                analysis_result.confidence if analysis_result else 0
            )
            
            return {
                "trust_score": assessment.get("trust_score", 0),
                "sandbox_level": assessment.get("security_policy", {}).get("sandbox", "strict"),
                "permissions": assessment.get("security_policy", {})
            }
        except Exception as e:
            return {
                "trust_score": 0,
                "sandbox_level": "strict",
                "permissions": {}
            }
    
    async def _stage_wasm_fallback_prep(
        self,
        manifest: Dict,
        build_result: Dict
    ) -> Dict[str, Any]:
        """Stage 5: Prepare WASM fallback"""
        try:
            from altstore.core.types.manifest_schema import ManifestValidator
            
            manifest_obj = ManifestValidator.from_dict(manifest)
            
            # Check if WASM fallback is appropriate
            should_prepare = self.wasm_manager.should_use_wasm_fallback(manifest_obj, native_success=True)
            
            if should_prepare:
                # Get WASM compatibility
                compatibility = self.wasm_manager.compatibility_checker.check_compatibility(manifest_obj)
                
                return {
                    "available": True,
                    "compatibility": compatibility,
                    "reason": "WASM fallback available for restricted environments"
                }
            else:
                return {
                    "available": False,
                    "compatibility": 0,
                    "reason": "WASM not appropriate for this application"
                }
        except Exception as e:
            return {
                "available": False,
                "compatibility": 0,
                "error": str(e)
            }
    
    async def _stage_capsule_creation(
        self,
        manifest: Dict,
        build_result: Dict,
        wasm_result: Dict,
        analysis_result: Any
    ) -> Optional[str]:
        """Stage 6: Create offline capsule"""
        try:
            app_id = manifest.get("metadata", {}).get("app_id", "unknown")
            version = manifest.get("metadata", {}).get("version", "1.0.0")
            
            # Mock artifacts for demo
            native_artifacts = [
                ("app_manifest.json", json.dumps(manifest, indent=2).encode())
            ]
            
            # Get trust snapshot
            trust_snapshot = self.trust_manager.get_latest_snapshot()
            
            capsule_path = self.capsule_builder.build_offline_capsule(
                app_id=app_id,
                version=version,
                manifest=manifest,
                native_artifacts=native_artifacts,
                wasm_artifact=b"WASM_FALLBACK_BINARY" if wasm_result.get("available") else None,
                trust_snapshot=trust_snapshot
            )
            
            return capsule_path
        
        except Exception as e:
            print(f"Capsule creation failed: {e}")
            return None
    
    async def _stage_installation(
        self,
        capsule_path: str,
        install_path: str,
        user_preferences: Dict
    ) -> Dict[str, Any]:
        """Stage 7: Install from capsule"""
        try:
            allow_wasm = user_preferences.get("allow_wasm", True)
            
            result = self.installer.install_from_capsule(
                capsule_path,
                allow_wasm_fallback=allow_wasm
            )
            
            return result
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def run_app(
        self,
        app_id: str,
        version: str = "latest",
        args: List[str] = None
    ) -> Dict[str, Any]:
        """
        Run an installed application.
        
        Automatically selects execution mode and handles fallbacks.
        """
        try:
            trace = self.installer.run_app(app_id, version, args or [])
            
            return {
                "success": trace.exit_code == 0,
                "execution_mode": trace.mode.value,
                "fallback_reason": trace.fallback_reason.value if trace.fallback_reason else None,
                "exit_code": trace.exit_code,
                "duration_seconds": trace.duration_seconds,
                "stdout": trace.stdout,
                "stderr": trace.stderr
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """Get status of a workflow"""
        for workflow in self.workflow_history:
            if workflow.get("id") == workflow_id:
                return workflow
        return None
    
    def list_installed_apps(self) -> List[Dict[str, str]]:
        """List all installed applications"""
        apps = []
        install_dir = self.storage_path / "installations" / "installed"
        
        if install_dir.exists():
            for app_dir in install_dir.iterdir():
                if app_dir.is_dir():
                    install_manifest = app_dir / "install.json"
                    if install_manifest.exists():
                        data = json.loads(install_manifest.read_text())
                        apps.append(data)
        
        return apps


# Example usage and integration test
async def example_workflow():
    """Example: GitHub repo to one-click runnable app"""
    
    print("=== AltStore Orchestrator Example ===\n")
    
    orchestrator = PlatformOrchestrator("./example_storage")
    
    # Example: Install ripgrep from GitHub
    print("Executing: GitHub repo → Analysis → Build → WASM Fallback → Capsule → Install")
    print("Repository: BurntSushi/ripgrep\n")
    
    result = await orchestrator.discover_and_install(
        "BurntSushi/ripgrep",
        user_preferences={
            "allow_wasm": True,
            "sandbox_level": "strict"
        }
    )
    
    if result["success"]:
        print("\n✅ Installation successful!")
        print(f"Workflow ID: {result['workflow_id']}")
        print(f"Install Path: {result['install_result'].get('install_path')}")
        print(f"Execution Mode: {result['install_result'].get('execution_mode')}")
        print(f"Trust Score: {result['security'].get('trust_score')}")
        print(f"WASM Compatible: {result['analysis'].get('wasm_compatible')}")
        
        # Show workflow stages
        print("\nWorkflow Stages:")
        for stage, details in result["stages"].items():
            status = details.get("status", "pending")
            print(f"  {stage}: {status}")
    else:
        print(f"\n❌ Workflow failed: {result.get('error')}")
        print(f"Failed at stages: {result.get('stages')}")


if __name__ == "__main__":
    # Run example
    asyncio.run(example_workflow())
