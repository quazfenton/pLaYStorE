"""
Integration test for the complete AltStore workflow.

Tests all major components working together:
- GitHub discovery
- Manifest generation
- Security assessment
- WASM fallback preparation
- Offline capsule creation
- Air-gapped installation

Run with: python -m pytest tests/integration_test.py -v
"""

import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path


class TestGitHubDiscovery:
    """Tests GitHub explorer functionality"""
    
    @pytest.mark.asyncio
    async def test_github_explorer_initialization(self):
        """Test GitHubExplorer can be initialized"""
        from playstorE.client.github_explorer import GitHubExplorer
        
        explorer = GitHubExplorer()
        assert explorer is not None
        assert explorer.base_url == "https://api.github.com"
    
    @pytest.mark.asyncio
    async def test_repo_classification(self):
        """Test repository type classification"""
        from playstorE.client.github_explorer import GitHubExplorer, RepoType
        
        explorer = GitHubExplorer()
        
        # Test CLI classification
        files = ["Cargo.toml", "Makefile", "src/main.rs"]
        readme = "A command-line tool for searching files. Usage: my-tool [FILES]"
        repo_type = explorer._classify_repo(files, readme)
        
        assert repo_type == RepoType.CLI_TOOL
    
    def test_port_detection(self):
        """Test port extraction from README"""
        from playstorE.client.github_explorer import GitHubExplorer
        
        explorer = GitHubExplorer()
        
        readme = """
        Start the server:
        python app.py --port 8000
        
        Access at http://localhost:8080
        
        WebSocket on port 5000
        """
        
        ports = explorer._detect_ports(readme)
        assert 8000 in ports
        assert 8080 in ports
        assert 5000 in ports


class TestManifestValidation:
    """Tests manifest schema and validation"""
    
    def test_manifest_creation_and_validation(self):
        """Test creating and validating a manifest"""
        from playstorE.core.types.manifest_schema import (
            AppManifest, Publisher, Source, Versions, Build, Run,
            Security, Trust, ManifestValidator, NetworkPolicy, FilesystemPolicy, RuntimeType
        )

        manifest = AppManifest(
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
                repo="test/app"
            ),
            versions=Versions(strategy="semver"),
            build=Build(strategy="docker"),
            run=Run(
                type=RuntimeType.CLI,
                entrypoint="app"
            ),
            security=Security(
                sandbox="strict",
                network=NetworkPolicy.NONE,
                filesystem=FilesystemPolicy.READONLY
            ),
            trust=Trust(verification="none")
        )
        
        # Validate
        assert ManifestValidator.validate(manifest.to_dict())
    
    def test_manifest_invalid_version(self):
        """Test manifest validation with invalid API version"""
        from playstorE.core.types.manifest_schema import ManifestValidator
        
        invalid_manifest = {
            "apiVersion": "invalid/v1",  # Invalid format
            "kind": "Application",
            "metadata": {"app_id": "test", "name": "test", "description": "test"},
            "publisher": {"name": "test", "verified_domains": []},
            "source": {"type": "github_repo"},
            "versions": {"strategy": "semver"},
            "build": {"strategy": "docker"},
            "run": {"type": "cli", "entrypoint": "app"},
            "security": {"sandbox": "strict", "network": "none", "filesystem": "readonly"},
            "trust": {"verification": "none"}
        }
        
        with pytest.raises(Exception):  # ValidationError
            ManifestValidator.validate(invalid_manifest)


class TestSecurityAssessment:
    """Tests security and trust scoring"""
    
    def test_trust_score_calculation(self):
        """Test trust score computation"""
        from playstorE.core.security.trust_model import SecurityManager
        from playstorE.core.types.manifest_schema import (
            AppManifest, Publisher, Source, Versions, Build, Run,
            Security, Trust, RuntimeType, NetworkPolicy, FilesystemPolicy
        )

        manager = SecurityManager()

        # Create mock manifest
        manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={"app_id": "test.app", "name": "Test"},
            publisher=Publisher(name="Test", verified_domains=["test.com"]),
            source=Source(type="github_repo", repo="test/app"),
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

        assessment = manager.assess_application(
            manifest,
            reproducibility_level="R2",  # High
            malware_result="safe",
            community_score=0.8
        )

        assert "trust_score" in assessment
        assert assessment["trust_score"] >= 0.0
        assert assessment["trust_score"] <= 1.0


class TestWASMFallback:
    """Tests WASM fallback system"""
    
    def test_wasm_compatibility_scoring(self):
        """Test WASM compatibility calculation"""
        from playstorE.executor.wasm import WASMCompatibilityChecker
        from playstorE.core.types.manifest_schema import (
            AppManifest, Publisher, Source, Versions, Build, Run,
            Security, Trust, NetworkPolicy, FilesystemPolicy
        )
        
        checker = WASMCompatibilityChecker()
        
        # Create a WASM-compatible manifest (Rust CLI)
        manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={"app_id": "test", "name": "test", "description": "test"},
            publisher=Publisher(name="test", verified_domains=[]),
            source=Source(type="github_repo"),
            versions=Versions(strategy="semver"),
            build=Build(strategy="native"),  # Native build (good for WASM)
            run=Run(type="cli", entrypoint="app"),  # CLI (compatible)
            security=Security(
                sandbox="strict",
                network=NetworkPolicy.NONE,
                filesystem=FilesystemPolicy.READONLY,
                allow_gpu=False  # No GPU (good for WASM)
            ),
            trust=Trust(verification="none")
        )
        
        score = checker.check_compatibility(manifest)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be reasonably compatible
    
    def test_wasm_fallback_manager(self):
        """Test WASM fallback decision logic"""
        from playstorE.executor.wasm import WASMFallbackManager
        from playstorE.core.types.manifest_schema import (
            AppManifest, Publisher, Source, Versions, Build, Run,
            Security, Trust, NetworkPolicy, FilesystemPolicy
        )
        
        manager = WASMFallbackManager()
        
        manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={"app_id": "test", "name": "test", "description": "test"},
            publisher=Publisher(name="test", verified_domains=[]),
            source=Source(type="github_repo"),
            versions=Versions(strategy="semver"),
            build=Build(strategy="native"),
            run=Run(type="cli", entrypoint="app"),
            security=Security(
                sandbox="strict",
                network=NetworkPolicy.NONE,
                filesystem=FilesystemPolicy.READONLY,
                allow_gpu=False
            ),
            trust=Trust(verification="none")
        )
        
        should_use = manager.should_use_wasm_fallback(manifest, native_success=False)
        assert isinstance(should_use, bool)


class TestOfflineCapsules:
    """Tests offline capsule creation and installation"""
    
    def test_capsule_creation(self):
        """Test building an offline capsule"""
        from playstorE.executor.offline_orchestrator import OfflineCapsuleBuilder
        
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = OfflineCapsuleBuilder(tmpdir)
            
            manifest = {
                "apiVersion": "appstore.dev/v1",
                "kind": "Application",
                "metadata": {
                    "app_id": "test.offline",
                    "name": "Offline Test",
                    "version": "1.0.0"
                }
            }
            
            native_artifacts = [
                ("app_binary", b"binary_content"),
                ("config.json", json.dumps({"version": "1.0.0"}).encode())
            ]
            
            capsule_path = builder.build_offline_capsule(
                app_id="test.offline",
                version="1.0.0",
                manifest=manifest,
                native_artifacts=native_artifacts,
                wasm_artifact=b"WASM_BINARY"
            )
            
            assert Path(capsule_path).exists()
            assert capsule_path.endswith(".capsule")
    
    def test_offline_installation(self):
        """Test installing from offline capsule"""
        from playstorE.executor.offline_orchestrator import (
            OfflineCapsuleBuilder, OfflineInstallationManager
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create capsule
            builder = OfflineCapsuleBuilder(tmpdir)
            
            manifest = {
                "apiVersion": "appstore.dev/v1",
                "kind": "Application",
                "metadata": {
                    "app_id": "test.offline",
                    "name": "Offline Test",
                    "version": "1.0.0"
                }
            }
            
            native_artifacts = [
                ("app_binary", b"binary_content")
            ]
            
            capsule_path = builder.build_offline_capsule(
                app_id="test.offline",
                version="1.0.0",
                manifest=manifest,
                native_artifacts=native_artifacts,
                wasm_artifact=b"WASM"
            )
            
            # Install from capsule
            installer = OfflineInstallationManager(tmpdir)
            result = installer.install_from_capsule(capsule_path)
            
            # Should succeed or fail gracefully
            assert "success" in result
            assert isinstance(result["success"], bool)


class TestFrontendUI:
    """Tests frontend UI generation"""
    
    def test_app_card_rendering(self):
        """Test app card HTML generation"""
        from playstorE.client.frontend import AppCard, TrustLevel
        
        card = AppCard(
            app_id="test.app",
            name="Test App",
            description="A test application",
            publisher="Test Publisher",
            trust_level=TrustLevel.VERIFIED,
            stars=100.0,
            download_count=1000,
            tags=["test", "demo"]
        )
        
        html = card.to_html()
        
        assert "Test App" in html
        assert "Test Publisher" in html
        assert "test-demo" in html or "test" in html
        assert "verified" in html.lower()
    
    def test_catalog_html_generation(self):
        """Test app catalog rendering"""
        from playstorE.client.frontend import AppCatalog, AppCard, TrustLevel
        
        catalog = AppCatalog()
        
        card1 = AppCard(
            app_id="app1",
            name="App 1",
            description="First app",
            publisher="Pub1",
            trust_level=TrustLevel.VERIFIED
        )
        
        card2 = AppCard(
            app_id="app2",
            name="App 2",
            description="Second app",
            publisher="Pub2",
            trust_level=TrustLevel.UNVERIFIED
        )
        
        catalog.add_category("Featured", [card1, card2])
        
        html = catalog.to_html()
        
        assert "App 1" in html
        assert "App 2" in html
        assert "Featured" in html
    
    def test_main_ui_generation(self):
        """Test main UI HTML generation"""
        from playstorE.client.frontend import MainUI
        
        ui = MainUI()
        html = ui.to_html()
        
        assert "AltStore" in html
        assert "Discover" in html
        assert "GitHub" in html
        assert "My Apps" in html


class TestCentralOrchestrator:
    """Tests the central orchestrator"""
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """Test orchestrator can be initialized"""
        from playstorE.core.orchestrator import PlatformOrchestrator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = PlatformOrchestrator(tmpdir)
            
            assert orchestrator is not None
            assert orchestrator.storage_path.exists()
            assert orchestrator.github_explorer is not None
            assert orchestrator.capsule_builder is not None
            assert orchestrator.installer is not None


class TestEndToEndIntegration:
    """High-level integration tests"""
    
    def test_manifest_to_capsule_pipeline(self):
        """Test complete pipeline from manifest to offline capsule"""
        from playstorE.core.types.manifest_schema import (
            AppManifest, Publisher, Source, Versions, Build, Run,
            Security, Trust, ManifestValidator, NetworkPolicy, FilesystemPolicy, RuntimeType
        )
        from playstorE.executor.offline_orchestrator import OfflineCapsuleBuilder
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create manifest
            manifest = AppManifest(
                api_version="appstore.dev/v1",
                kind="Application",
                metadata={
                    "app_id": "test.e2e",
                    "name": "E2E Test",
                    "description": "End-to-end test"
                },
                publisher=Publisher(
                    name="Test Pub",
                    verified_domains=[]
                ),
                source=Source(type="github_repo", repo="test/test"),
                versions=Versions(strategy="semver"),
                build=Build(strategy="docker"),
                run=Run(type=RuntimeType.CLI, entrypoint="test"),
                security=Security(
                    sandbox="strict",
                    network=NetworkPolicy.NONE,
                    filesystem=FilesystemPolicy.READONLY
                ),
                trust=Trust(verification="none")
            )
            
            # Validate
            assert ManifestValidator.validate(manifest.to_dict())
            
            # Create capsule
            builder = OfflineCapsuleBuilder(tmpdir)
            capsule_path = builder.build_offline_capsule(
                app_id="test.e2e",
                version="1.0.0",
                manifest=manifest.to_dict(),
                native_artifacts=[("app", b"test")],
                wasm_artifact=b"WASM"
            )
            
            # Verify capsule created
            assert Path(capsule_path).exists()


# Performance and stress tests
class TestPerformance:
    """Performance-related tests"""
    
    def test_manifest_validation_performance(self):
        """Test manifest validation performance"""
        import time
        from playstorE.core.types.manifest_schema import ManifestValidator
        
        manifest = {
            "apiVersion": "appstore.dev/v1",
            "kind": "Application",
            "metadata": {"app_id": "perf.test", "name": "test", "description": "test"},
            "publisher": {"name": "test", "verified_domains": []},
            "source": {"type": "github_repo"},
            "versions": {"strategy": "semver"},
            "build": {"strategy": "docker"},
            "run": {"type": "cli", "entrypoint": "app"},
            "security": {"sandbox": "strict", "network": "none", "filesystem": "readonly"},
            "trust": {"verification": "none"}
        }
        
        start = time.time()
        for _ in range(100):
            ManifestValidator.validate(manifest)
        duration = time.time() - start
        
        # Should validate 100 manifests in < 1 second
        assert duration < 1.0
        print(f"Validated 100 manifests in {duration:.3f}s")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
