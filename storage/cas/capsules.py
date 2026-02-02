"""
Offline-first architecture and capsule system for the alternative app store platform.
Implements offline installation and distribution of applications with verification.
Based on the scouts.md specification for offline-first architecture.
"""
import os
import json
import hashlib
import tarfile
import tempfile
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import zipfile
from pathlib import Path
import shutil

# Handle cryptography import with fallback
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    # Mock cryptography classes if not available
    class MockPrivateKey:
        def sign(self, data, padding, algorithm):
            return b"mock_signature"

    class MockPublicKey:
        def verify(self, signature, data, padding, algorithm):
            pass  # Always succeed in mock

    def generate_private_key(public_exponent, key_size):
        return MockPrivateKey()

    def PKCS1v15():
        return None

    class SHA256:
        pass

    InvalidSignature = Exception
    CRYPTO_AVAILABLE = False

from altstore.core.types.manifest_schema import AppManifest
from altstore.core.security.reproducible_builds import BuildResult


@dataclass
class CapsuleMetadata:
    """Metadata for an installation capsule"""
    capsule_id: str
    app_id: str
    version: str
    platform: str
    manifest_hash: str
    artifact_hashes: List[str]
    signature: str
    timestamp: str
    trust_score: float
    reproducibility_level: str
    dependencies: List[str]


class ContentAddressableStorage:
    """Content addressable storage for offline artifacts"""
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.blobs_path = self.storage_path / "blobs" / "sha256"
        self.blobs_path.mkdir(parents=True, exist_ok=True)
    
    def store_content(self, content: bytes) -> str:
        """Store content and return its SHA256 hash"""
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Create subdirectories based on first 2 characters of hash
        subdir = self.blobs_path / content_hash[:2]
        subdir.mkdir(exist_ok=True)
        
        # Store content in file named after full hash
        file_path = subdir / content_hash[2:]  # Skip first 2 chars since they form directory
        with open(file_path, 'wb') as f:
            f.write(content)
        
        return f"sha256:{content_hash}"
    
    def retrieve_content(self, content_hash: str) -> Optional[bytes]:
        """Retrieve content by its hash"""
        if not content_hash.startswith("sha256:"):
            return None
        
        hash_value = content_hash[7:]  # Remove "sha256:" prefix
        file_path = self.blobs_path / hash_value[:2] / hash_value[2:]
        
        if file_path.exists():
            with open(file_path, 'rb') as f:
                return f.read()
        return None
    
    def has_content(self, content_hash: str) -> bool:
        """Check if content exists in storage"""
        if not content_hash.startswith("sha256:"):
            return False
        
        hash_value = content_hash[7:]
        file_path = self.blobs_path / hash_value[:2] / hash_value[2:]
        return file_path.exists()


class CapsuleBuilder:
    """Builds installation capsules for offline distribution"""
    
    def __init__(self, cas_storage: ContentAddressableStorage):
        self.cas = cas_storage
        if CRYPTO_AVAILABLE:
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            self.public_key = self.private_key.public_key()
        else:
            # Use mock keys when cryptography is not available
            self.private_key = generate_private_key(65537, 2048)
            self.public_key = MockPublicKey()
    
    def build_capsule(self, manifest: AppManifest, build_result: BuildResult, 
                     platform: str = "universal") -> str:
        """
        Build an installation capsule for offline distribution.
        
        Args:
            manifest: App manifest
            build_result: Build result with artifacts
            platform: Target platform
            
        Returns:
            Path to the created capsule file
        """
        # Create temporary directory for capsule contents
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Store manifest in CAS
            manifest_data = json.dumps(manifest.to_dict(), indent=2).encode()
            manifest_hash = self.cas.store_content(manifest_data)
            
            # Store build artifacts in CAS
            artifact_hashes = []
            for artifact_path in build_result.normalized_artifacts:
                with open(artifact_path, 'rb') as f:
                    artifact_data = f.read()
                artifact_hash = self.cas.store_content(artifact_data)
                artifact_hashes.append(artifact_hash)
            
            # Create capsule metadata
            capsule_id = f"cap_{manifest.metadata['app_id']}_{manifest.metadata.get('version', '1.0.0')}_{platform}"
            metadata = CapsuleMetadata(
                capsule_id=capsule_id,
                app_id=manifest.metadata["app_id"],
                version=manifest.metadata.get("version", "1.0.0"),
                platform=platform,
                manifest_hash=manifest_hash,
                artifact_hashes=artifact_hashes,
                signature="",
                timestamp=datetime.utcnow().isoformat() + "Z",
                trust_score=0.8,  # Placeholder - would come from trust system
                reproducibility_level=build_result.reproducibility_level.value,
                dependencies=manifest.dependencies or []
            )
            
            # Serialize metadata
            metadata_dict = {
                "capsule_id": metadata.capsule_id,
                "app_id": metadata.app_id,
                "version": metadata.version,
                "platform": metadata.platform,
                "manifest_hash": metadata.manifest_hash,
                "artifact_hashes": metadata.artifact_hashes,
                "timestamp": metadata.timestamp,
                "trust_score": metadata.trust_score,
                "reproducibility_level": metadata.reproducibility_level,
                "dependencies": metadata.dependencies
            }
            
            # Sign the metadata
            metadata_json = json.dumps(metadata_dict, sort_keys=True).encode()
            
            if CRYPTO_AVAILABLE:
                signature = self.private_key.sign(
                    metadata_json,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
            else:
                # Create a mock signature when cryptography is not available
                signature = hashlib.sha256(metadata_json).digest()
            
            metadata.signature = signature.hex()
            
            # Update metadata with signature
            metadata_dict["signature"] = metadata.signature
            
            # Create capsule archive
            capsule_path = temp_path / f"{capsule_id}.cap"
            
            with zipfile.ZipFile(capsule_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add metadata
                zipf.writestr("metadata.json", json.dumps(metadata_dict, indent=2))
                
                # Add manifest (already in CAS, but include for convenience)
                zipf.writestr("manifest.yaml", json.dumps(manifest.to_dict(), indent=2))
                
                # Add checksums
                checksums = {
                    "manifest": manifest_hash,
                    "artifacts": artifact_hashes
                }
                zipf.writestr("checksums.json", json.dumps(checksums, indent=2))
                
                # Add trust information
                trust_info = {
                    "verification_status": "signed",
                    "reproducibility_level": build_result.reproducibility_level.value,
                    "build_recipe_hash": build_result.recipe_hash
                }
                zipf.writestr("trust.json", json.dumps(trust_info, indent=2))
            
            # Copy capsule to final location
            final_capsule_path = f"{capsule_id}.cap"
            shutil.copy2(capsule_path, final_capsule_path)
            
            return final_capsule_path
    
    def verify_capsule_integrity(self, capsule_path: str) -> Tuple[bool, str, Optional[CapsuleMetadata]]:
        """
        Verify the integrity of a capsule.
        
        Args:
            capsule_path: Path to the capsule file
            
        Returns:
            Tuple of (is_valid, message, metadata)
        """
        try:
            with zipfile.ZipFile(capsule_path, 'r') as zipf:
                # Extract metadata
                metadata_content = zipf.read("metadata.json").decode()
                metadata_dict = json.loads(metadata_content)
                
                # Verify signature
                signature_hex = metadata_dict.pop("signature", "")
                if not signature_hex:
                    return False, "No signature found in capsule", None
                
                metadata_json = json.dumps(metadata_dict, sort_keys=True).encode()
                
                if CRYPTO_AVAILABLE:
                    try:
                        self.public_key.verify(
                            bytes.fromhex(signature_hex),
                            metadata_json,
                            padding.PKCS1v15(),
                            hashes.SHA256()
                        )
                    except InvalidSignature:
                        return False, "Invalid signature", None
                else:
                    # Fail verification if cryptography is not available
                    # This prevents tampered capsules from passing verification
                    return False, "Cryptography unavailable - cannot verify signature", None
                
                # Reconstruct metadata object
                metadata = CapsuleMetadata(
                    capsule_id=metadata_dict["capsule_id"],
                    app_id=metadata_dict["app_id"],
                    version=metadata_dict["version"],
                    platform=metadata_dict["platform"],
                    manifest_hash=metadata_dict["manifest_hash"],
                    artifact_hashes=metadata_dict["artifact_hashes"],
                    signature=signature_hex,
                    timestamp=metadata_dict["timestamp"],
                    trust_score=metadata_dict["trust_score"],
                    reproducibility_level=metadata_dict["reproducibility_level"],
                    dependencies=metadata_dict["dependencies"]
                )
                
                # Verify content hashes
                for artifact_hash in metadata.artifact_hashes:
                    if not self.cas.has_content(artifact_hash):
                        return False, f"Missing artifact: {artifact_hash}", metadata
                
                if not self.cas.has_content(metadata.manifest_hash):
                    return False, f"Missing manifest: {metadata.manifest_hash}", metadata
                
                return True, "Capsule verified successfully", metadata
                
        except zipfile.BadZipFile:
            return False, "Invalid capsule file format", None
        except KeyError as e:
            return False, f"Missing required field in capsule: {e}", None
        except Exception as e:
            return False, f"Error verifying capsule: {e}", None


class CapsuleVerifier:
    """Verifies capsule integrity and authenticity using a known public key"""

    def __init__(self, cas_storage: ContentAddressableStorage, public_key=None):
        self.cas = cas_storage
        self.public_key = public_key

    def verify_capsule_integrity(self, capsule_path: str, public_key=None) -> Tuple[bool, str, Optional[CapsuleMetadata]]:
        """
        Verify the integrity of a capsule using a specific public key.

        Args:
            capsule_path: Path to the capsule file
            public_key: Public key to use for verification (overrides instance key if provided)

        Returns:
            Tuple of (is_valid, message, metadata)
        """
        try:
            with zipfile.ZipFile(capsule_path, 'r') as zipf:
                # Extract metadata
                metadata_content = zipf.read("metadata.json").decode()
                metadata_dict = json.loads(metadata_content)

                # Verify signature
                signature_hex = metadata_dict.pop("signature", "")
                if not signature_hex:
                    return False, "No signature found in capsule", None

                metadata_json = json.dumps(metadata_dict, sort_keys=True).encode()

                # Use provided public key or instance public key
                verification_key = public_key or self.public_key

                if CRYPTO_AVAILABLE and verification_key:
                    try:
                        verification_key.verify(
                            bytes.fromhex(signature_hex),
                            metadata_json,
                            padding.PKCS1v15(),
                            hashes.SHA256()
                        )
                    except InvalidSignature:
                        return False, "Invalid signature", None
                elif not CRYPTO_AVAILABLE:
                    # Fail verification if cryptography is not available
                    # This prevents tampered capsules from passing verification
                    return False, "Cryptography unavailable - cannot verify signature", None
                else:
                    # No public key provided for verification
                    return False, "Public key not provided for signature verification", None

                # Reconstruct metadata object
                metadata = CapsuleMetadata(
                    capsule_id=metadata_dict["capsule_id"],
                    app_id=metadata_dict["app_id"],
                    version=metadata_dict["version"],
                    platform=metadata_dict["platform"],
                    manifest_hash=metadata_dict["manifest_hash"],
                    artifact_hashes=metadata_dict["artifact_hashes"],
                    signature=signature_hex,
                    timestamp=metadata_dict["timestamp"],
                    trust_score=metadata_dict["trust_score"],
                    reproducibility_level=metadata_dict["reproducibility_level"],
                    dependencies=metadata_dict["dependencies"]
                )

                # Verify content hashes
                for artifact_hash in metadata.artifact_hashes:
                    if not self.cas.has_content(artifact_hash):
                        return False, f"Missing artifact: {artifact_hash}", metadata

                if not self.cas.has_content(metadata.manifest_hash):
                    return False, f"Missing manifest: {metadata.manifest_hash}", metadata

                return True, "Capsule verified successfully", metadata

        except zipfile.BadZipFile:
            return False, "Invalid capsule file format", None
        except KeyError as e:
            return False, f"Missing required field in capsule: {e}", None
        except Exception as e:
            return False, f"Error verifying capsule: {e}", None


class OfflineInstaller:
    """Installs applications from offline capsules"""

    def __init__(self, cas_storage: ContentAddressableStorage, public_key=None):
        self.cas = cas_storage
        self.verifier = CapsuleVerifier(cas_storage, public_key)

    def install_from_capsule(self, capsule_path: str, install_path: str, public_key=None) -> Tuple[bool, str, Optional[AppManifest]]:
        """
        Install an application from an offline capsule.

        Args:
            capsule_path: Path to the capsule file
            install_path: Path to install the application
            public_key: Public key to use for verification (optional)

        Returns:
            Tuple of (success, message, manifest)
        """
        # Verify capsule integrity first
        is_valid, message, metadata = self.verifier.verify_capsule_integrity(capsule_path, public_key)
        if not is_valid:
            return False, f"Invalid capsule: {message}", None

        try:
            # Create installation directory
            install_dir = Path(install_path)
            install_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(capsule_path, 'r') as zipf:
                # Extract manifest
                manifest_content = zipf.read("manifest.yaml").decode()
                manifest_dict = json.loads(manifest_content)

                # Reconstruct manifest object
                from altstore.core.types.manifest_schema import ManifestValidator
                manifest = ManifestValidator.from_dict(manifest_dict)

                # Extract and install artifacts
                for i, artifact_hash in enumerate(metadata.artifact_hashes):
                    artifact_data = self.cas.retrieve_content(artifact_hash)
                    if artifact_data is None:
                        return False, f"Artifact not found in storage: {artifact_hash}", None

                    # Write artifact to installation directory
                    artifact_filename = f"artifact_{i}"
                    artifact_path = install_dir / artifact_filename
                    with open(artifact_path, 'wb') as f:
                        f.write(artifact_data)

                # Create installation manifest
                install_manifest = {
                    "installed_at": datetime.utcnow().isoformat() + "Z",
                    "capsule_id": metadata.capsule_id,
                    "app_id": metadata.app_id,
                    "version": metadata.version,
                    "manifest_hash": metadata.manifest_hash,
                    "artifact_hashes": metadata.artifact_hashes,
                    "trust_score": metadata.trust_score,
                    "reproducibility_level": metadata.reproducibility_level
                }

                with open(install_dir / "install_manifest.json", 'w') as f:
                    json.dump(install_manifest, f, indent=2)

                return True, f"Successfully installed {metadata.app_id} version {metadata.version}", manifest

        except Exception as e:
            return False, f"Installation failed: {e}", None


class CapsuleManager:
    """Main manager for capsule operations"""

    def __init__(self, storage_path: str = "./capsule_storage"):
        self.cas = ContentAddressableStorage(storage_path)
        self.builder = CapsuleBuilder(self.cas)
        # Share the same public key between builder and installer
        self.installer = OfflineInstaller(self.cas, self.builder.public_key if CRYPTO_AVAILABLE else None)
    
    def create_capsule(self, manifest: AppManifest, build_result: BuildResult, 
                      platform: str = "universal") -> str:
        """Create a capsule from manifest and build result"""
        return self.builder.build_capsule(manifest, build_result, platform)
    
    def verify_capsule(self, capsule_path: str) -> Tuple[bool, str, Optional[CapsuleMetadata]]:
        """Verify a capsule's integrity and authenticity"""
        # Create a verifier with the builder's public key to verify capsules created by this manager
        verifier = CapsuleVerifier(self.cas, self.builder.public_key if CRYPTO_AVAILABLE else None)
        return verifier.verify_capsule_integrity(capsule_path)
    
    def install_capsule(self, capsule_path: str, install_path: str) -> Tuple[bool, str, Optional[AppManifest]]:
        """Install an application from a capsule"""
        return self.installer.install_from_capsule(capsule_path, install_path)
    
    def export_capsule_for_distribution(self, capsule_path: str, output_path: str) -> bool:
        """Export a capsule to a specific location for distribution"""
        try:
            shutil.copy2(capsule_path, output_path)
            return True
        except Exception as e:
            print(f"Failed to export capsule: {e}")
            return False
    
    def import_capsule_from_distribution(self, source_path: str, destination_path: str) -> bool:
        """Import a capsule from a distribution source"""
        try:
            shutil.copy2(source_path, destination_path)
            return True
        except Exception as e:
            print(f"Failed to import capsule: {e}")
            return False


# Example usage and test
if __name__ == "__main__":
    from altstore.core.types.manifest_schema import (
        AppManifest, Publisher, Source, Versions, Build, Run,
        Security, Trust, Resources
    )
    from altstore.core.security.reproducible_builds import BuildResult, ReproducibilityLevel
    
    # Create a capsule manager
    capsule_manager = CapsuleManager("./test_capsule_storage")
    
    # Create a test manifest
    test_manifest = AppManifest(
        api_version="appstore.dev/v1",
        kind="Application",
        metadata={
            "app_id": "test.offline-app",
            "name": "Offline Test App",
            "description": "A test application for offline installation",
            "version": "1.0.0"
        },
        publisher=Publisher(
            name="Offline Publisher",
            verified_domains=["offline-pub.com"]
        ),
        source=Source(
            type="github_repo",
            repo="offline-pub/offline-app"
        ),
        versions=Versions(strategy="semver"),
        build=Build(
            strategy="docker",
            commands=["echo 'Building offline app'"]
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
        trust=Trust(verification="R2"),
        resources=Resources(cpu_limit=0.5, memory_limit_mb=512)
    )
    
    # Create a mock build result
    build_result = BuildResult(
        success=True,
        output_dir="/tmp/mock_build",
        hash="sha256:mockbuildhash1234567890abcdef",
        recipe_hash="sha256:mockrecipehash0987654321fedcba",
        reproducibility_level=ReproducibilityLevel.R2,
        log="Mock build log",
        normalized_artifacts=["/tmp/mock_artifact.bin"]
    )
    
    # Create a temporary artifact file for the build result
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as temp_artifact:
        temp_artifact.write(b"Mock application binary content")
        build_result.normalized_artifacts = [temp_artifact.name]
    
    try:
        # Create a capsule
        print("Creating capsule...")
        capsule_path = capsule_manager.create_capsule(test_manifest, build_result)
        print(f"Capsule created: {capsule_path}")
        
        # Verify the capsule
        print("\nVerifying capsule...")
        is_valid, message, metadata = capsule_manager.verify_capsule(capsule_path)
        print(f"Verification result: {is_valid}, message: {message}")
        if metadata:
            print(f"Capsule metadata: {metadata.app_id}, version: {metadata.version}")
        
        # Install the capsule
        print("\nInstalling capsule...")
        install_result, install_msg, installed_manifest = capsule_manager.install_capsule(
            capsule_path, "./test_install_dir"
        )
        print(f"Installation result: {install_result}, message: {install_msg}")
        
        if installed_manifest:
            print(f"Installed manifest app: {installed_manifest.metadata['name']}")
        
        # Clean up
        import os
        if os.path.exists(capsule_path):
            os.remove(capsule_path)
        if os.path.exists("./test_install_dir"):
            import shutil
            shutil.rmtree("./test_install_dir")
        if os.path.exists(temp_artifact.name):
            os.remove(temp_artifact.name)
        
    except Exception as e:
        print(f"Error during capsule operations: {e}")
        # Clean up in case of error
        import os
        if 'capsule_path' in locals() and os.path.exists(capsule_path):
            os.remove(capsule_path)
        if os.path.exists("./test_install_dir"):
            import shutil
            shutil.rmtree("./test_install_dir")
        if 'temp_artifact' in locals() and os.path.exists(temp_artifact.name):
            os.remove(temp_artifact.name)
    
    print("\nCleaning up storage...")
    import shutil
    if os.path.exists("./test_capsule_storage"):
        shutil.rmtree("./test_capsule_storage")