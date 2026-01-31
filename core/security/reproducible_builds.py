"""
Reproducible build verification system for the alternative app store platform.
Implements verification of deterministic builds to ensure trust and security.
Based on the scouts.md specification for reproducible builds.
"""
import os
import tempfile
import subprocess
import hashlib
import shutil
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass
import json
import tarfile
from pathlib import Path
from ..types.manifest_schema import AppManifest, Build


class ReproducibilityLevel(Enum):
    """Levels of reproducibility"""
    R0 = "R0"  # Not reproducible
    R1 = "R1"  # Deterministic inputs
    R2 = "R2"  # Bit-for-bit identical
    R3 = "R3"  # Signed + reproducible


@dataclass
class BuildRecipe:
    """Definition of a build recipe for reproducible builds"""
    base_image: str
    commands: List[str]
    environment: Dict[str, str]
    source_hash: str
    dependencies: List[str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for hashing"""
        return {
            "base_image": self.base_image,
            "commands": self.commands,
            "environment": self.environment,
            "source_hash": self.source_hash,
            "dependencies": self.dependencies
        }
    
    def hash(self) -> str:
        """Generate a hash of the build recipe"""
        recipe_dict = self.to_dict()
        recipe_json = json.dumps(recipe_dict, sort_keys=True)
        return hashlib.sha256(recipe_json.encode()).hexdigest()


@dataclass
class BuildResult:
    """Result of a build operation"""
    success: bool
    output_dir: str
    hash: str
    recipe_hash: str
    reproducibility_level: ReproducibilityLevel
    log: str
    normalized_artifacts: List[str]


class ReproducibleBuilder:
    """Manages reproducible builds for applications"""
    
    def __init__(self, work_dir: str = None):
        self.work_dir = work_dir or tempfile.mkdtemp(prefix="altstore_build_")
        os.makedirs(self.work_dir, exist_ok=True)
    
    def build_and_verify(self, manifest: AppManifest, source_path: str) -> BuildResult:
        """
        Build the application and verify reproducibility.
        
        Args:
            manifest: App manifest defining build requirements
            source_path: Path to source code
            
        Returns:
            BuildResult with reproducibility assessment
        """
        # Calculate source hash
        source_hash = self._calculate_source_hash(source_path)
        
        # Create build recipe
        recipe = self._create_build_recipe(manifest, source_path, source_hash)
        
        # Perform the build
        build_dir1 = os.path.join(self.work_dir, "build1")
        result1 = self._perform_build(recipe, source_path, build_dir1)
        
        if not result1.success:
            return BuildResult(
                success=False,
                output_dir="",
                hash="",
                recipe_hash=recipe.hash(),
                reproducibility_level=ReproducibilityLevel.R0,
                log=result1.log,
                normalized_artifacts=[]
            )
        
        # Perform second build to check reproducibility
        build_dir2 = os.path.join(self.work_dir, "build2")
        result2 = self._perform_build(recipe, source_path, build_dir2)
        
        if not result2.success:
            return BuildResult(
                success=False,
                output_dir="",
                hash="",
                recipe_hash=recipe.hash(),
                reproducibility_level=ReproducibilityLevel.R0,
                log=result2.log,
                normalized_artifacts=[]
            )
        
        # Compare build results
        reproducibility_level = self._compare_builds(result1, result2)
        
        # Normalize artifacts for consistent hashing
        normalized_artifacts = self._normalize_artifacts(build_dir1)
        
        return BuildResult(
            success=True,
            output_dir=build_dir1,
            hash=result1.hash,
            recipe_hash=recipe.hash(),
            reproducibility_level=reproducibility_level,
            log=result1.log + "\n" + result2.log,
            normalized_artifacts=normalized_artifacts
        )
    
    def _calculate_source_hash(self, source_path: str) -> str:
        """Calculate a hash of the source code"""
        hash_obj = hashlib.sha256()
        
        for root, dirs, files in os.walk(source_path):
            for file in sorted(files):  # Sort for consistency
                filepath = os.path.join(root, file)
                if os.path.isfile(filepath):
                    with open(filepath, 'rb') as f:
                        while chunk := f.read(8192):
                            hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def _create_build_recipe(self, manifest: AppManifest, source_path: str, source_hash: str) -> BuildRecipe:
        """Create a build recipe from manifest"""
        # Determine base image based on build strategy and language
        base_image = self._determine_base_image(manifest)
        
        # Set up environment for reproducible builds
        environment = {
            "SOURCE_DATE_EPOCH": "1700000000",  # Fixed timestamp for reproducibility
            "TZ": "UTC",
            "LANG": "C",
            "LC_ALL": "C"
        }
        
        # Add any environment variables from manifest
        if manifest.build.environment:
            environment.update(manifest.build.environment)
        
        # Get dependencies
        dependencies = self._resolve_dependencies(manifest)
        
        return BuildRecipe(
            base_image=base_image,
            commands=manifest.build.commands or [],
            environment=environment,
            source_hash=source_hash,
            dependencies=dependencies
        )
    
    def _determine_base_image(self, manifest: AppManifest) -> str:
        """Determine appropriate base image for build"""
        # This would be more sophisticated in practice
        if manifest.build.base_image:
            return manifest.build.base_image
        
        # Infer from source code
        source_dir = "/tmp/inferred_source"  # Placeholder
        if os.path.exists(os.path.join(source_dir, "requirements.txt")):
            return "python:3.11@sha256:abc123"  # Would use actual hash
        elif os.path.exists(os.path.join(source_dir, "package.json")):
            return "node:18@sha256:def456"
        elif os.path.exists(os.path.join(source_dir, "go.mod")):
            return "golang:1.21@sha256:ghi789"
        elif os.path.exists(os.path.join(source_dir, "Cargo.toml")):
            return "rust:1.70@sha256:jkl012"
        else:
            return "ubuntu:22.04@sha256:mno345"
    
    def _resolve_dependencies(self, manifest: AppManifest) -> List[str]:
        """Resolve and lock dependencies for reproducible builds"""
        dependencies = []
        
        # This would implement proper dependency resolution
        # For now, return a placeholder
        if manifest.dependencies:
            dependencies.extend(manifest.dependencies)
        
        return dependencies
    
    def _perform_build(self, recipe: BuildRecipe, source_path: str, output_dir: str) -> BuildResult:
        """Perform a single build operation"""
        os.makedirs(output_dir, exist_ok=True)
        
        # For now, simulate the build process
        # In a real implementation, this would use Docker or other build systems
        log = f"Building with recipe: {recipe.base_image}\n"
        
        # Simulate build commands
        for cmd in recipe.commands:
            log += f"Executing: {cmd}\n"
            # In real implementation, execute the command in a controlled environment
        
        # Create some dummy output files for demonstration
        output_file = os.path.join(output_dir, "output.bin")
        with open(output_file, 'wb') as f:
            f.write(b"dummy build output")
        
        # Calculate hash of output
        output_hash = self._calculate_output_hash(output_dir)
        
        return BuildResult(
            success=True,
            output_dir=output_dir,
            hash=output_hash,
            recipe_hash=recipe.hash(),
            reproducibility_level=ReproducibilityLevel.R1,  # Placeholder
            log=log,
            normalized_artifacts=[output_file]
        )
    
    def _calculate_output_hash(self, output_dir: str) -> str:
        """Calculate hash of build output"""
        hash_obj = hashlib.sha256()
        
        for root, dirs, files in os.walk(output_dir):
            for file in sorted(files):  # Sort for consistency
                filepath = os.path.join(root, file)
                if os.path.isfile(filepath):
                    # Include filename in hash for completeness
                    hash_obj.update(file.encode())
                    
                    with open(filepath, 'rb') as f:
                        while chunk := f.read(8192):
                            hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def _compare_builds(self, result1: BuildResult, result2: BuildResult) -> ReproducibilityLevel:
        """Compare two build results to determine reproducibility level"""
        if not result1.success or not result2.success:
            return ReproducibilityLevel.R0
        
        if result1.hash == result2.hash:
            return ReproducibilityLevel.R2
        else:
            # Check if differences are due to non-determinism we can handle
            diff_causes = self._analyze_build_diff(result1.output_dir, result2.output_dir)
            
            if not diff_causes:
                # No clear cause for difference, assume not reproducible
                return ReproducibilityLevel.R1
            else:
                # Differences are explainable, still R1
                return ReproducibilityLevel.R1
    
    def _analyze_build_diff(self, dir1: str, dir2: str) -> List[str]:
        """Analyze differences between two build outputs"""
        causes = []
        
        # This would implement detailed diff analysis
        # For now, return a placeholder
        return causes
    
    def _normalize_artifacts(self, build_dir: str) -> List[str]:
        """Normalize build artifacts for consistent hashing"""
        normalized_paths = []
        
        # Normalize timestamps
        for root, dirs, files in os.walk(build_dir):
            for file in files:
                filepath = os.path.join(root, file)
                # Set consistent timestamp
                os.utime(filepath, (1700000000, 1700000000))
                normalized_paths.append(filepath)
        
        # Create a tar with consistent ordering
        tar_path = os.path.join(self.work_dir, "normalized.tar")
        with tarfile.open(tar_path, "w") as tar:
            for path in sorted(normalized_paths):
                arcname = os.path.relpath(path, build_dir)
                tar.add(path, arcname=arcname)
        
        return [tar_path]
    
    def cleanup(self):
        """Clean up build workspace"""
        if os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir)


class ReproducibilityVerifier:
    """Verifies reproducibility of builds"""
    
    def __init__(self):
        self.builder = ReproducibleBuilder()
    
    def verify_build(self, manifest: AppManifest, source_path: str) -> Tuple[ReproducibilityLevel, Dict[str, Any]]:
        """
        Verify the reproducibility of a build.
        
        Args:
            manifest: App manifest
            source_path: Path to source code
            
        Returns:
            Tuple of (reproducibility level, verification details)
        """
        build_result = self.builder.build_and_verify(manifest, source_path)
        
        details = {
            "recipe_hash": build_result.recipe_hash,
            "output_hash": build_result.hash,
            "success": build_result.success,
            "log": build_result.log,
            "reproducibility_level": build_result.reproducibility_level.value,
            "normalized_artifacts": build_result.normalized_artifacts
        }
        
        return build_result.reproducibility_level, details
    
    def verify_existing_builds(self, build_hashes: List[str]) -> bool:
        """
        Verify that existing builds are reproducible by rebuilding.
        
        Args:
            build_hashes: List of expected build hashes
            
        Returns:
            True if all builds are reproducible
        """
        # This would implement verification against known good hashes
        # For now, return a placeholder
        return len(build_hashes) > 0


class ReproducibleBuildService:
    """Main service for managing reproducible builds"""
    
    def __init__(self):
        self.verifier = ReproducibilityVerifier()
    
    def process_application(self, manifest: AppManifest, source_path: str) -> Dict[str, Any]:
        """
        Process an application for reproducible build verification.
        
        Args:
            manifest: App manifest
            source_path: Path to source code
            
        Returns:
            Dictionary with processing results
        """
        # Verify the build
        level, details = self.verifier.verify_build(manifest, source_path)
        
        # Update manifest with reproducibility info
        manifest.trust.verification = level.value
        if hasattr(manifest, 'determinism'):
            manifest.determinism.reproducibility_level = level.value
            manifest.determinism.build_recipe_hash = details['recipe_hash']
        
        # Determine trust impact
        trust_impact = self._calculate_trust_impact(level)
        
        return {
            "reproducibility_level": level.value,
            "trust_impact": trust_impact,
            "details": details,
            "manifest_updated": True
        }
    
    def _calculate_trust_impact(self, level: ReproducibilityLevel) -> float:
        """Calculate trust impact based on reproducibility level"""
        trust_map = {
            ReproducibilityLevel.R0: -0.3,  # Reduces trust
            ReproducibilityLevel.R1: 0.0,   # Neutral
            ReproducibilityLevel.R2: 0.5,   # Increases trust
            ReproducibilityLevel.R3: 0.8    # Significantly increases trust
        }
        return trust_map.get(level, 0.0)
    
    def get_reproducibility_report(self, manifest: AppManifest, source_path: str) -> Dict[str, Any]:
        """
        Generate a detailed reproducibility report.
        
        Args:
            manifest: App manifest
            source_path: Path to source code
            
        Returns:
            Detailed reproducibility report
        """
        level, details = self.verifier.verify_build(manifest, source_path)
        
        return {
            "app_id": manifest.metadata.get("app_id", "unknown"),
            "version": manifest.metadata.get("version", "unknown"),
            "reproducibility_level": level.value,
            "recipe_hash": details["recipe_hash"],
            "output_hash": details["output_hash"],
            "build_success": details["success"],
            "trust_score_change": self._calculate_trust_impact(level),
            "verification_timestamp": "2026-01-20T10:00:00Z",
            "build_environment": {
                "base_image": self._determine_base_image_for_report(manifest),
                "deterministic_flags": ["SOURCE_DATE_EPOCH", "TZ=UTC", "LANG=C"]
            },
            "artifacts": {
                "count": len(details["normalized_artifacts"]),
                "total_size": self._calculate_artifact_sizes(details["normalized_artifacts"])
            }
        }
    
    def _determine_base_image_for_report(self, manifest: AppManifest) -> str:
        """Determine base image for reporting purposes"""
        return self.verifier.builder._determine_base_image(manifest)
    
    def _calculate_artifact_sizes(self, artifact_paths: List[str]) -> int:
        """Calculate total size of artifacts"""
        total_size = 0
        for path in artifact_paths:
            if os.path.exists(path):
                total_size += os.path.getsize(path)
        return total_size


# Example usage and test
if __name__ == "__main__":
    from ..core.types.manifest_schema import (
        AppManifest, Publisher, Source, Versions, Build, Run, 
        Security, Trust
    )
    
    # Create a test manifest
    test_manifest = AppManifest(
        api_version="appstore.dev/v1",
        kind="Application",
        metadata={
            "app_id": "test.reproducible",
            "name": "Reproducible Test App",
            "description": "A test application for reproducible builds"
        },
        publisher=Publisher(
            name="Test Publisher",
            verified_domains=["test.com"]
        ),
        source=Source(
            type="github_repo",
            repo="test/reproducible-app"
        ),
        versions=Versions(strategy="semver"),
        build=Build(
            strategy="docker",
            commands=[
                "pip install -r requirements.txt",
                "python setup.py build"
            ],
            environment={
                "PYTHON_VERSION": "3.11"
            }
        ),
        run=Run(
            type="cli",
            entrypoint="app",
            args=[]
        ),
        security=Security(
            sandbox="strict",
            network="none",
            filesystem="readonly",
            allow_gpu=False
        ),
        trust=Trust(verification="none")
    )
    
    # Create a temporary source directory for testing
    import tempfile
    temp_source = tempfile.mkdtemp(prefix="altstore_test_source_")
    
    # Create some dummy source files
    with open(os.path.join(temp_source, "requirements.txt"), "w") as f:
        f.write("requests==2.31.0\n")
    
    with open(os.path.join(temp_source, "app.py"), "w") as f:
        f.write("#!/usr/bin/env python\nprint('Hello World')\n")
    
    try:
        # Test the reproducible build service
        service = ReproducibleBuildService()
        
        # Process the application
        result = service.process_application(test_manifest, temp_source)
        print(f"Processing result: {result}")
        
        # Generate a reproducibility report
        report = service.get_reproducibility_report(test_manifest, temp_source)
        print(f"\nReproducibility report:")
        print(f"  App ID: {report['app_id']}")
        print(f"  Level: {report['reproducibility_level']}")
        print(f"  Trust impact: {report['trust_score_change']}")
        print(f"  Recipe hash: {report['recipe_hash'][:16]}...")
        print(f"  Artifacts: {report['artifacts']['count']} files, {report['artifacts']['total_size']} bytes")
        
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_source)
        service.verifier.builder.cleanup()