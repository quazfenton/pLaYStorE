"""
Build Cache Tests

Tests for the build cache system:
- Cache key computation
- Cache hit/miss behavior
- Cache invalidation
- Cache metrics
- TTL expiration
- LRU eviction
"""

import pytest
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from playstorE.core.build_cache import (
    BuildCache,
    CacheEntry,
    CacheMetrics,
    get_build_cache,
    reset_build_cache
)


class TestCacheKeyComputation:
    """Test content-addressable cache key computation"""
    
    def test_cache_key_is_deterministic(self):
        """Same inputs should produce same cache key"""
        cache = BuildCache("./test_cache_key")
        
        key1 = cache.compute_cache_key(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=["npm install", "npm build"],
            manifest={"source": {"repo": "user/repo"}}
        )
        
        key2 = cache.compute_cache_key(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=["npm install", "npm build"],
            manifest={"source": {"repo": "user/repo"}}
        )
        
        assert key1 == key2
    
    def test_cache_key_changes_with_repo(self):
        """Different repos should produce different cache keys"""
        cache = BuildCache("./test_cache_key")
        
        key1 = cache.compute_cache_key(
            repo="https://github.com/user/repo1",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={}
        )
        
        key2 = cache.compute_cache_key(
            repo="https://github.com/user/repo2",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={}
        )
        
        assert key1 != key2
    
    def test_cache_key_changes_with_commit(self):
        """Different commits should produce different cache keys"""
        cache = BuildCache("./test_cache_key")
        
        key1 = cache.compute_cache_key(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={}
        )
        
        key2 = cache.compute_cache_key(
            repo="https://github.com/user/repo",
            commit="def456",
            build_strategy="docker",
            build_commands=[],
            manifest={}
        )
        
        assert key1 != key2
    
    def test_cache_key_changes_with_build_commands(self):
        """Different build commands should produce different cache keys"""
        cache = BuildCache("./test_cache_key")
        
        key1 = cache.compute_cache_key(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=["npm install"],
            manifest={}
        )
        
        key2 = cache.compute_cache_key(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=["yarn install"],
            manifest={}
        )
        
        assert key1 != key2
    
    def test_cache_key_changes_with_manifest(self):
        """Different manifests should produce different cache keys"""
        cache = BuildCache("./test_cache_key")
        
        key1 = cache.compute_cache_key(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={"version": "1.0.0"}
        )
        
        key2 = cache.compute_cache_key(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={"version": "2.0.0"}
        )
        
        assert key1 != key2


class TestCacheHitMiss:
    """Test cache hit/miss behavior"""
    
    def setup_method(self):
        """Create fresh cache for each test"""
        reset_build_cache()
        self.cache = BuildCache("./test_cache_hitmiss", ttl_days=30, max_size_mb=100)
    
    def teardown_method(self):
        """Clean up test cache"""
        import shutil
        if Path("./test_cache_hitmiss").exists():
            shutil.rmtree("./test_cache_hitmiss")
        reset_build_cache()
    
    def test_cache_miss_on_first_request(self):
        """First request should be a cache miss"""
        result = self.cache.get(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={}
        )
        
        assert result is None
        assert self.cache.get_metrics().misses == 1
    
    def test_cache_hit_after_put(self):
        """Should hit cache after storing result"""
        # Store in cache
        build_result = {"hash": "test123", "build_path": "/tmp/test"}
        artifact_dir = Path("/tmp/test_artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "artifact.txt").write_text("test")
        
        self.cache.put(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=["npm install"],
            manifest={"source": {"repo": "user/repo"}},
            build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        # Retrieve from cache
        result = self.cache.get(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=["npm install"],
            manifest={"source": {"repo": "user/repo"}}
        )
        
        assert result is not None
        assert result.repo == "https://github.com/user/repo"
        assert result.commit == "abc123"
        assert self.cache.get_metrics().hits == 1
    
    def test_cache_miss_on_different_commit(self):
        """Different commit should be a cache miss"""
        # Store in cache
        build_result = {"hash": "test123", "build_path": "/tmp/test"}
        artifact_dir = Path("/tmp/test_artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache.put(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={},
            build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        # Different commit should miss
        result = self.cache.get(
            repo="https://github.com/user/repo",
            commit="def456",
            build_strategy="docker",
            build_commands=[],
            manifest={}
        )
        
        assert result is None


class TestCacheInvalidation:
    """Test cache invalidation strategies"""
    
    def setup_method(self):
        reset_build_cache()
        self.cache = BuildCache("./test_cache_invalidate", ttl_days=30, max_size_mb=100)
    
    def teardown_method(self):
        import shutil
        if Path("./test_cache_invalidate").exists():
            shutil.rmtree("./test_cache_invalidate")
        reset_build_cache()
    
    def test_invalidate_by_repo(self):
        """Invalidating by repo should remove all entries for that repo"""
        # Add multiple entries for same repo
        build_result = {"hash": "test123", "build_path": "/tmp/test"}
        artifact_dir = Path("/tmp/test_artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache.put(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={},
            build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        self.cache.put(
            repo="https://github.com/user/repo",
            commit="def456",
            build_strategy="docker",
            build_commands=[],
            manifest={},
            build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        # Add entry for different repo
        self.cache.put(
            repo="https://github.com/user/other",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={},
            build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        # Invalidate first repo
        count = self.cache.invalidate("https://github.com/user/repo")
        
        assert count == 2
        assert self.cache.get_metrics().entry_count == 1
    
    def test_invalidate_by_commit(self):
        """Invalidating by commit should remove only that commit"""
        build_result = {"hash": "test123", "build_path": "/tmp/test"}
        artifact_dir = Path("/tmp/test_artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache.put(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={},
            build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        self.cache.put(
            repo="https://github.com/user/repo",
            commit="def456",
            build_strategy="docker",
            build_commands=[],
            manifest={},
            build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        # Invalidate specific commit
        count = self.cache.invalidate("https://github.com/user/repo", commit="abc123")
        
        assert count == 1
        assert self.cache.get_metrics().entry_count == 1


class TestCacheMetrics:
    """Test cache metrics tracking"""
    
    def setup_method(self):
        reset_build_cache()
        self.cache = BuildCache("./test_cache_metrics", ttl_days=30, max_size_mb=100)
    
    def teardown_method(self):
        import shutil
        if Path("./test_cache_metrics").exists():
            shutil.rmtree("./test_cache_metrics")
        reset_build_cache()
    
    def test_hit_rate_calculation(self):
        """Hit rate should be hits / (hits + misses)"""
        # Generate some hits and misses
        for i in range(3):
            self.cache.get(repo=f"repo{i}", commit="abc", build_strategy="docker", build_commands=[], manifest={})
        
        # Add one entry
        build_result = {"hash": "test123", "build_path": "/tmp/test"}
        artifact_dir = Path("/tmp/test_artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        self.cache.put(
            repo="repo0", commit="abc", build_strategy="docker",
            build_commands=[], manifest={}, build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        # Generate hits
        for i in range(7):
            self.cache.get(repo="repo0", commit="abc", build_strategy="docker", build_commands=[], manifest={})
        
        metrics = self.cache.get_metrics()
        
        assert metrics.hits == 7
        assert metrics.misses == 3
        assert abs(metrics.hit_rate - 0.7) < 0.01
    
    def test_metrics_to_dict(self):
        """Metrics should convert to dictionary for API responses"""
        metrics = CacheMetrics(hits=10, misses=5, evictions=2, total_size_bytes=1024000, entry_count=5)
        
        result = metrics.to_dict()
        
        assert result["hits"] == 10
        assert result["misses"] == 5
        assert result["hit_rate"] == pytest.approx(0.6667, rel=0.01)
        assert result["total_size_mb"] == pytest.approx(0.977, rel=0.01)


class TestCacheEviction:
    """Test cache eviction policies"""
    
    def setup_method(self):
        reset_build_cache()
        # Small cache size to trigger eviction
        self.cache = BuildCache("./test_cache_eviction", ttl_days=30, max_size_mb=1)
    
    def teardown_method(self):
        import shutil
        if Path("./test_cache_eviction").exists():
            shutil.rmtree("./test_cache_eviction")
        reset_build_cache()
    
    def test_lru_eviction_on_size_limit(self):
        """Should evict LRU entries when cache is full"""
        build_result = {"hash": "test123", "build_path": "/tmp/test"}
        artifact_dir = Path("/tmp/test_artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a file that's 300KB
        large_file = artifact_dir / "large.bin"
        large_file.write_bytes(b"x" * (300 * 1024))
        
        # Add multiple entries
        for i in range(5):
            self.cache.put(
                repo=f"https://github.com/user/repo{i}",
                commit="abc123",
                build_strategy="docker",
                build_commands=[],
                manifest={},
                build_result=build_result,
                artifact_dir=str(artifact_dir)
            )
            time.sleep(0.1)  # Ensure different access times
        
        # Access first entry to make it recently used
        self.cache.get(
            repo="https://github.com/user/repo0",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={}
        )
        
        # Add new entry - should evict entry 1, 2, or 3 (not 0 which was just accessed)
        self.cache.put(
            repo="https://github.com/user/repo_new",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={},
            build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        metrics = self.cache.get_metrics()
        assert metrics.evictions > 0


class TestCacheExpiration:
    """Test TTL-based cache expiration"""
    
    def setup_method(self):
        reset_build_cache()
        # Very short TTL for testing
        self.cache = BuildCache("./test_cache_expiry", ttl_days=0, max_size_mb=100)
    
    def teardown_method(self):
        import shutil
        if Path("./test_cache_expiry").exists():
            shutil.rmtree("./test_cache_expiry")
        reset_build_cache()
    
    def test_expired_entry_not_returned(self):
        """Expired entries should not be returned"""
        build_result = {"hash": "test123", "build_path": "/tmp/test"}
        artifact_dir = Path("/tmp/test_artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # Add entry
        self.cache.put(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={},
            build_result=build_result,
            artifact_dir=str(artifact_dir)
        )
        
        # Manually expire the entry by modifying its TTL
        cache_key = self.cache.compute_cache_key(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={}
        )
        
        entry = self.cache._index.get(cache_key)
        if entry:
            # Set created_at to 2 days ago (TTL is 0 days)
            from datetime import timedelta
            entry.created_at = (datetime.now() - timedelta(days=2)).isoformat()
            self.cache._save_index()
        
        # Should be a cache miss now
        result = self.cache.get(
            repo="https://github.com/user/repo",
            commit="abc123",
            build_strategy="docker",
            build_commands=[],
            manifest={}
        )
        
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
