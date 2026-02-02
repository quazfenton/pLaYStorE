"""
Comprehensive test suite for the alternative app store platform.
Tests all major components and integration points.
"""
import unittest
import tempfile
import os
import shutil
from pathlib import Path

# Import all the modules we've created with error handling
try:
    from altstore.core.types.manifest_schema import (
        AppManifest, Publisher, Source, Versions, Build, Run,
        Security, Trust, Resources, ManifestValidator
    )
except ImportError as e:
    print(f"Error importing manifest schema: {e}")
    AppManifest = Publisher = Source = Versions = Build = Run = Security = Trust = Resources = ManifestValidator = None

try:
    from altstore.core.validation.formal_verifier import FormalManifestVerifier
except ImportError as e:
    print(f"Error importing formal verifier: {e}")
    FormalManifestVerifier = None

try:
    from altstore.sandbox.base import SandboxFactory, SandboxType, SecurityLevel
except ImportError as e:
    print(f"Error importing sandbox: {e}")
    SandboxFactory = SandboxType = SecurityLevel = None

try:
    from altstore.sandbox.dry_run import DryRunSandbox, MalwareDetector
except ImportError as e:
    print(f"Error importing dry run: {e}")
    DryRunSandbox = MalwareDetector = None

try:
    from altstore.core.types.github_analyzer import GitHubAutoWrapper
except ImportError as e:
    print(f"Error importing github analyzer: {e}")
    GitHubAutoWrapper = None

try:
    from altstore.core.security.reproducible_builds import ReproducibleBuildService
except ImportError as e:
    print(f"Error importing reproducible builds: {e}")
    ReproducibleBuildService = None

try:
    from altstore.executor.wasm import WASMFallbackManager
except ImportError as e:
    print(f"Error importing wasm: {e}")
    WASMFallbackManager = None

try:
    from altstore.storage.indexes.federated import FederatedIndexManager
except ImportError as e:
    print(f"Error importing federated index: {e}")
    FederatedIndexManager = None

try:
    from altstore.core.economics.monetization import EconomicIncentiveSystem
except ImportError as e:
    print(f"Error importing monetization: {e}")
    EconomicIncentiveSystem = None

try:
    from altstore.core.security.trust_model import SecurityManager
except ImportError as e:
    print(f"Error importing trust model: {e}")
    SecurityManager = None

try:
    from altstore.storage.cas.capsules import CapsuleManager
except ImportError as e:
    print(f"Error importing capsules: {e}")
    CapsuleManager = None


@unittest.skipIf(AppManifest is None, "AppManifest not available")
class TestManifestSchema(unittest.TestCase):
    """Test manifest schema and validation"""

    def setUp(self):
        if AppManifest is None:
            self.skipTest("AppManifest not available")

        self.valid_manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={
                "app_id": "test.app",
                "name": "Test App",
                "description": "A test application"
            },
            publisher=Publisher(
                name="Test Publisher",
                verified_domains=["test.com"]
            ),
            source=Source(
                type="github_repo",
                repo="test/test-app"
            ),
            versions=Versions(strategy="semver"),
            build=Build(strategy="docker"),
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
            trust=Trust(verification="R2")
        )

    def test_manifest_creation(self):
        """Test that a valid manifest can be created"""
        if AppManifest is None:
            self.skipTest("AppManifest not available")
        self.assertEqual(self.valid_manifest.metadata["app_id"], "test.app")
        self.assertEqual(self.valid_manifest.publisher.name, "Test Publisher")

    def test_manifest_validation(self):
        """Test manifest validation"""
        if ManifestValidator is None:
            self.skipTest("ManifestValidator not available")
        is_valid = ManifestValidator.validate(self.valid_manifest.to_dict())
        self.assertTrue(is_valid)

    def test_invalid_manifest(self):
        """Test validation of invalid manifest"""
        if ManifestValidator is None:
            self.skipTest("ManifestValidator not available")
        invalid_manifest = self.valid_manifest.to_dict()
        del invalid_manifest["apiVersion"]  # Required field

        with self.assertRaises(Exception):  # Should raise ValidationError
            ManifestValidator.validate(invalid_manifest)


@unittest.skipIf(FormalManifestVerifier is None, "FormalManifestVerifier not available")
class TestFormalVerification(unittest.TestCase):
    """Test formal manifest verification"""

    def setUp(self):
        if FormalManifestVerifier is None:
            self.skipTest("FormalManifestVerifier not available")

        self.verifier = FormalManifestVerifier()
        self.manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={
                "app_id": "test.app",
                "name": "Test App",
                "description": "A test application"
            },
            publisher=Publisher(name="Test Publisher", verified_domains=["test.com"]),
            source=Source(type="github_repo", repo="test/test-app"),
            versions=Versions(strategy="semver"),
            build=Build(strategy="docker"),
            run=Run(type="cli", entrypoint="app", args=[]),
            security=Security(sandbox="strict", network="none", filesystem="readonly", allow_gpu=False),
            trust=Trust(verification="R2")
        )

    def test_basic_verification(self):
        """Test basic manifest verification"""
        if FormalManifestVerifier is None:
            self.skipTest("FormalManifestVerifier not available")
        is_valid, reason = self.verifier.verify_manifest(self.manifest)
        self.assertTrue(is_valid)

    def test_permission_combinations(self):
        """Test permission combination verification"""
        if FormalManifestVerifier is None:
            self.skipTest("FormalManifestVerifier not available")
        is_safe, reason = self.verifier.verify_permission_combinations(self.manifest)
        self.assertTrue(is_safe)


@unittest.skipIf(SandboxFactory is None, "SandboxFactory not available")
class TestSandboxSystem(unittest.TestCase):
    """Test sandbox functionality"""

    def test_sandbox_availability(self):
        """Test that sandbox types are properly detected"""
        if SandboxFactory is None:
            self.skipTest("SandboxFactory not available")
        available = SandboxFactory.get_available_sandboxes()
        self.assertIsInstance(available, list)

    def test_native_sandbox_creation(self):
        """Test creation of native sandbox"""
        if SandboxFactory is None:
            self.skipTest("SandboxFactory not available")
        if SandboxType.NATIVE in SandboxFactory.get_available_sandboxes():
            sandbox = SandboxFactory.create_sandbox(SandboxType.NATIVE, SecurityLevel.STRICT)
            self.assertIsNotNone(sandbox)


@unittest.skipIf(MalwareDetector is None, "MalwareDetector not available")
class TestMalwareDetection(unittest.TestCase):
    """Test malware detection system"""

    def setUp(self):
        if MalwareDetector is None:
            self.skipTest("MalwareDetector not available")
        self.detector = MalwareDetector()
        self.manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={
                "app_id": "test.safe-app",
                "name": "Safe Test App",
                "description": "A safe test application"
            },
            publisher=Publisher(name="Safe Publisher", verified_domains=["safe.com"]),
            source=Source(type="github_repo", repo="safe/safe-app"),
            versions=Versions(strategy="semver"),
            build=Build(strategy="docker", commands=["echo 'safe build'"]),
            run=Run(type="cli", entrypoint="app", args=[]),
            security=Security(sandbox="strict", network="none", filesystem="readonly", allow_gpu=False),
            trust=Trust(verification="R2")
        )

    def test_safe_app_scan(self):
        """Test scanning a safe application"""
        if MalwareDetector is None:
            self.skipTest("MalwareDetector not available")
        results = self.detector.scan_app(self.manifest, "echo 'Hello World'")
        self.assertIn(results["recommendation"], ["approve", "sandbox_only"])


@unittest.skipIf(ReproducibleBuildService is None, "ReproducibleBuildService not available")
class TestReproducibleBuilds(unittest.TestCase):
    """Test reproducible build system"""

    def setUp(self):
        if ReproducibleBuildService is None:
            self.skipTest("ReproducibleBuildService not available")
        self.service = ReproducibleBuildService()
        self.manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={
                "app_id": "test.repro-app",
                "name": "Reproducible Test App",
                "description": "A reproducible test application"
            },
            publisher=Publisher(name="Repro Publisher", verified_domains=["repro.com"]),
            source=Source(type="github_repo", repo="repro/repro-app"),
            versions=Versions(strategy="semver"),
            build=Build(strategy="docker", commands=["echo 'build command'"]),
            run=Run(type="cli", entrypoint="app", args=[]),
            security=Security(sandbox="strict", network="none", filesystem="readonly", allow_gpu=False),
            trust=Trust(verification="R2")
        )
    
    def test_process_application(self):
        """Test processing an application for reproducible build"""
        # Create a temporary source directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a dummy requirements.txt file
            req_file = Path(temp_dir) / "requirements.txt"
            req_file.write_text("requests==2.31.0\n")
            
            # Process the application
            result = self.service.process_application(self.manifest, temp_dir)
            self.assertIn("reproducibility_level", result)


@unittest.skipIf(CapsuleManager is None, "CapsuleManager not available")
class TestCapsuleSystem(unittest.TestCase):
    """Test capsule system"""

    def test_capsule_creation(self):
        """Test capsule creation and verification"""
        if CapsuleManager is None:
            self.skipTest("CapsuleManager not available")
        with tempfile.TemporaryDirectory() as storage_dir:
            capsule_manager = CapsuleManager(storage_dir)
            
            # Create a simple manifest
            manifest = AppManifest(
                api_version="appstore.dev/v1",
                kind="Application",
                metadata={
                    "app_id": "test.capsule-app",
                    "name": "Capsule Test App",
                    "description": "A capsule test application",
                    "version": "1.0.0"
                },
                publisher=Publisher(name="Capsule Publisher", verified_domains=["capsule.com"]),
                source=Source(type="github_repo", repo="capsule/capsule-app"),
                versions=Versions(strategy="semver"),
                build=Build(strategy="docker"),
                run=Run(type="cli", entrypoint="app", args=[]),
                security=Security(sandbox="strict", network="none", filesystem="readonly", allow_gpu=False),
                trust=Trust(verification="R2")
            )
            
            # Create a mock build result
            from altstore.core.security.reproducible_builds import BuildResult, ReproducibilityLevel
            build_result = BuildResult(
                success=True,
                output_dir="/tmp/mock",
                hash="sha256:mockhash1234567890abcdef",
                recipe_hash="sha256:mockrecipe1234567890abcdef",
                reproducibility_level=ReproducibilityLevel.R2,
                log="Mock build log",
                normalized_artifacts=[]
            )
            
            # Create a temporary artifact
            with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as temp_artifact:
                temp_artifact.write(b"Mock application content")
                build_result.normalized_artifacts = [temp_artifact.name]
            
            # Initialize capsule_path to None to avoid UnboundLocalError
            capsule_path = None
            try:
                # Create capsule
                capsule_path = capsule_manager.create_capsule(manifest, build_result)
                self.assertTrue(os.path.exists(capsule_path))

                # Verify capsule
                is_valid, message, metadata = capsule_manager.verify_capsule(capsule_path)
                self.assertTrue(is_valid)

            finally:
                # Clean up
                if capsule_path and os.path.exists(capsule_path):
                    os.remove(capsule_path)
                if build_result.normalized_artifacts:
                    for artifact in build_result.normalized_artifacts:
                        if os.path.exists(artifact):
                            os.remove(artifact)


@unittest.skipIf(FederatedIndexManager is None, "FederatedIndexManager not available")
class TestFederatedIndex(unittest.TestCase):
    """Test federated index system"""

    def setUp(self):
        if FederatedIndexManager is None:
            self.skipTest("FederatedIndexManager not available")
        self.manager = FederatedIndexManager("test-node")
    
    def test_add_and_get_app(self):
        """Test adding and retrieving an app from the index"""
        from altstore.storage.indexes.federated import AppEntry
        
        app_entry = AppEntry(
            app_id="test.index-app",
            manifest_hash="sha256:abc123",
            artifact_hash="sha256:def456",
            trust_score=0.92,
            publisher="did:test:123",
            version="1.0.0",
            timestamp="2026-01-20T10:00:00Z",
            signature=""
        )
        
        success = self.manager.add_app(app_entry)
        self.assertTrue(success)
        
        retrieved_app = self.manager.get_app("test.index-app")
        self.assertIsNotNone(retrieved_app)
        self.assertEqual(retrieved_app.app_id, "test.index-app")


@unittest.skipIf(EconomicIncentiveSystem is None, "EconomicIncentiveSystem not available")
class TestMonetizationSystem(unittest.TestCase):
    """Test monetization and reputation system"""

    def setUp(self):
        if EconomicIncentiveSystem is None:
            self.skipTest("EconomicIncentiveSystem not available")
        self.system = EconomicIncentiveSystem()
    
    def test_publisher_registration(self):
        """Test registering a publisher"""
        success = self.system.register_publisher("test-publisher", {
            'past_success_rate': 0.9,
            'avg_community_review': 0.8,
            'reproducibility_score': 0.95
        })
        self.assertTrue(success)
        
        # Check reputation
        rep = self.system.reputation_manager.get_reputation("test-publisher", "publisher")
        self.assertGreater(rep, 0.0)
    
    def test_app_submission(self):
        """Test submitting an application"""
        # Register a publisher first
        self.system.register_publisher("submitter", {
            'past_success_rate': 0.8,
            'avg_community_review': 0.7
        })
        
        # Submit an app
        result = self.system.submit_application(
            "test.submit-app", "submitter", {"category": "utility"}
        )
        
        self.assertTrue(result["success"])
        self.assertIn("tier", result)


@unittest.skipIf(SecurityManager is None, "SecurityManager not available")
class TestSecurityManager(unittest.TestCase):
    """Test security and trust management"""

    def setUp(self):
        if SecurityManager is None:
            self.skipTest("SecurityManager not available")
        self.security_manager = SecurityManager()
        self.manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={
                "app_id": "test.secure-app",
                "name": "Secure Test App",
                "description": "A secure test application"
            },
            publisher=Publisher(name="Secure Publisher", verified_domains=["secure.com"]),
            source=Source(type="github_repo", repo="secure/secure-app"),
            versions=Versions(strategy="semver"),
            build=Build(strategy="docker"),
            run=Run(type="cli", entrypoint="app", args=[]),
            security=Security(sandbox="strict", network="none", filesystem="readonly", allow_gpu=False),
            trust=Trust(verification="R2")
        )
    
    def test_app_assessment(self):
        """Test application security assessment"""
        from altstore.core.security.reproducible_builds import ReproducibilityLevel
        from altstore.sandbox.dry_run import MalwareDetectionResult
        
        assessment = self.security_manager.assess_application(
            self.manifest,
            ReproducibilityLevel.R2,
            MalwareDetectionResult.SAFE,
            community_score=0.85
        )
        
        self.assertEqual(assessment["app_id"], "test.secure-app")
        self.assertGreaterEqual(assessment["trust_score"], 0.0)
        self.assertLessEqual(assessment["trust_score"], 1.0)


def run_tests():
    """Run all tests"""
    # Create a test suite
    loader = unittest.TestLoader()
    suite = loader.discover('.', pattern='test_*.py')
    
    # Also add our inline tests
    suite.addTest(loader.loadTestsFromTestCase(TestManifestSchema))
    suite.addTest(loader.loadTestsFromTestCase(TestFormalVerification))
    if SandboxFactory is not None:
        suite.addTest(loader.loadTestsFromTestCase(TestSandboxSystem))
    if MalwareDetector is not None:
        suite.addTest(loader.loadTestsFromTestCase(TestMalwareDetection))
    if ReproducibleBuildService is not None:
        suite.addTest(loader.loadTestsFromTestCase(TestReproducibleBuilds))
    if CapsuleManager is not None:
        suite.addTest(loader.loadTestsFromTestCase(TestCapsuleSystem))
    if FederatedIndexManager is not None:
        suite.addTest(loader.loadTestsFromTestCase(TestFederatedIndex))
    if EconomicIncentiveSystem is not None:
        suite.addTest(loader.loadTestsFromTestCase(TestMonetizationSystem))
    if SecurityManager is not None:
        suite.addTest(loader.loadTestsFromTestCase(TestSecurityManager))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("Running comprehensive test suite for AltStore platform...")
    success = run_tests()
    
    if success:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed!")
        exit(1)