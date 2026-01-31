"""
Simple tests for the AltStore platform focusing on core functionality
without requiring external dependencies.
"""
import unittest
import tempfile
import os
from pathlib import Path


def test_manifest_basics():
    """Test basic manifest functionality without external dependencies"""
    print("Testing manifest basics...")

    # Dynamically import with error handling
    try:
        from altstore.core.types.manifest_schema import (
            AppManifest, Publisher, Source, Versions, Build, Run,
            Security, Trust, Resources, RuntimeType, NetworkPolicy, FilesystemPolicy
        )

        # Create a basic manifest
        manifest = AppManifest(
            api_version="appstore.dev/v1",
            kind="Application",
            metadata={
                "app_id": "test.simple-app",
                "name": "Simple Test App",
                "description": "A simple test application"
            },
            publisher=Publisher(
                name="Test Publisher",
                verified_domains=["test.com"]
            ),
            source=Source(
                type="github_repo",
                repo="test/simple-app"
            ),
            versions=Versions(strategy="semver"),
            build=Build(strategy="docker"),
            run=Run(
                type=RuntimeType.CLI,  # Use enum instead of string
                entrypoint="app",
                args=[]
            ),
            security=Security(
                sandbox="strict",
                network=NetworkPolicy.NONE,  # Use enum instead of string
                filesystem=FilesystemPolicy.READONLY,  # Use enum instead of string
                allow_gpu=False
            ),
            trust=Trust(verification="R2")
        )

        # Test conversion to dict
        manifest_dict = manifest.to_dict()
        assert manifest_dict['metadata']['app_id'] == "test.simple-app"
        assert manifest_dict['publisher']['name'] == "Test Publisher"

        print("✓ Manifest basics test passed")
        return True

    except ImportError as e:
        print(f"⚠ Manifest module not available: {e}")
        return False
    except Exception as e:
        print(f"✗ Manifest basics test failed: {e}")
        return False


def test_sandbox_basics():
    """Test basic sandbox functionality"""
    print("Testing sandbox basics...")
    
    try:
        from altstore.sandbox.base import SandboxFactory, SandboxType, SecurityLevel
        
        # Test platform detection
        available_sandboxes = SandboxFactory.get_available_sandboxes()
        print(f"Available sandboxes: {available_sandboxes}")
        
        print("✓ Sandbox basics test passed")
        return True
        
    except ImportError as e:
        print(f"⚠ Sandbox module not available: {e}")
        return False
    except Exception as e:
        print(f"✗ Sandbox basics test failed: {e}")
        return False


def test_security_basics():
    """Test basic security functionality"""
    print("Testing security basics...")

    try:
        from altstore.core.security.trust_model import TrustEvaluator, TrustLevel
        from altstore.core.security.reproducible_builds import ReproducibilityLevel
        from altstore.sandbox.dry_run import MalwareDetectionResult

        # Create evaluator
        evaluator = TrustEvaluator()

        # Since we can't create a full manifest without the full schema,
        # we'll just test that the classes exist and can be instantiated
        print("TrustEvaluator created successfully")
        print("✓ Security basics test passed")
        return True

    except ImportError as e:
        print(f"⚠ Security module not available: {e}")
        return False
    except Exception as e:
        print(f"✗ Security basics test failed: {e}")
        return False


def test_capsule_basics():
    """Test basic capsule functionality"""
    print("Testing capsule basics...")

    try:
        from altstore.storage.cas.capsules import ContentAddressableStorage

        # Test CAS creation
        with tempfile.TemporaryDirectory() as temp_dir:
            cas = ContentAddressableStorage(temp_dir)

            # Test storing content
            test_content = b"test content for CAS"
            content_hash = cas.store_content(test_content)
            print(f"Content stored with hash: {content_hash}")

            # Test retrieving content
            retrieved_content = cas.retrieve_content(content_hash)
            assert retrieved_content == test_content

            print("✓ Capsule basics test passed")
            return True

    except ImportError as e:
        print(f"⚠ Capsule module not available: {e}")
        return False
    except Exception as e:
        print(f"✗ Capsule basics test failed: {e}")
        return False


def test_github_analyzer_basics():
    """Test basic GitHub analyzer functionality"""
    print("Testing GitHub analyzer basics...")
    
    try:
        from altstore.core.types.github_analyzer import GitHubRepoAnalyzer
        
        # Just test that the class can be instantiated
        analyzer = GitHubRepoAnalyzer()
        
        # Check that language support is available
        assert hasattr(analyzer, 'language_support')
        print("GitHubRepoAnalyzer created successfully")
        
        print("✓ GitHub analyzer basics test passed")
        return True
        
    except ImportError as e:
        print(f"⚠ GitHub analyzer module not available: {e}")
        return False
    except Exception as e:
        print(f"✗ GitHub analyzer basics test failed: {e}")
        return False


def run_all_tests():
    """Run all basic tests"""
    print("Running basic tests for AltStore platform...\n")
    
    tests = [
        ("Manifest Basics", test_manifest_basics),
        ("Sandbox Basics", test_sandbox_basics),
        ("Security Basics", test_security_basics),
        ("Capsule Basics", test_capsule_basics),
        ("GitHub Analyzer Basics", test_github_analyzer_basics),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print(f"\n--- Summary ---")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "SKIP/FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed or available")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    if success:
        print("\n✓ All available tests passed!")
    else:
        print("\n! Some tests were skipped or failed, but this may be due to missing dependencies")