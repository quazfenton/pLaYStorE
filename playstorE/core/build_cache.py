"""
Build Cache System for AltStore Platform.

Provides:
- Content-addressable build cache
- Cache invalidation strategies
- Cache hit/miss metrics
- Automatic cache cleanup

This prevents rebuilding unchanged repositories and speeds up repeated installations.
"""

import hashlib
import json
import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Metadata for a cached build"""
    cache_key: str
    repo: str
    commit: str
    build_strategy: str
    build_hash: str
    artifact_paths: List[str]
    created_at: str
    last_accessed: str
    access_count: int
    manifest_hash: str
    build_commands_hash: str
    size_bytes: int
    ttl_days: int = 30  # Default 30 day TTL


@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0
    oldest_entry: Optional[str] = None
    newest_entry: Optional[str] = None
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": round(self.hit_rate, 4),
            "total_size_bytes": self.total_size_bytes,
            "total_size_mb": round(self.total_size_bytes / (1024 * 1024), 2),
            "entry_count": self.entry_count,
            "oldest_entry": self.oldest_entry,
            "newest_entry": self.newest_entry
        }


class BuildCache:
    """
    Content-addressable build cache with automatic invalidation.
    
    Cache keys are computed from:
    - Repository URL
    - Commit hash
    - Build strategy (docker, npm, cargo, etc.)
    - Build commands
    - Manifest configuration
    
    This ensures cache invalidation when any relevant input changes.
    """
    
    def __init__(self, cache_path: str = "./build_cache", ttl_days: int = 30, max_size_mb: int = 1000):
        self.cache_path = Path(cache_path).resolve()
        self.artifacts_path = self.cache_path / "artifacts"
        self.metadata_path = self.cache_path / "metadata"
        self.ttl_days = ttl_days
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        # Thread-safe metrics
        self._lock = threading.RLock()
        self._metrics = CacheMetrics()
        
        # In-memory index for fast lookups
        self._index: Dict[str, CacheEntry] = {}
        
        # Create cache directories
        self._initialize_cache()
        
        logger.info(f"Build cache initialized at {self.cache_path}")
        logger.info(f"Cache TTL: {ttl_days} days, Max size: {max_size_mb}MB")
    
    def _initialize_cache(self):
        """Initialize cache directories and load existing index"""
        self.artifacts_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing index
        index_file = self.metadata_path / "index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    index_data = json.load(f)
                    for key, entry_data in index_data.items():
                        self._index[key] = CacheEntry(**entry_data)
                
                self._update_metrics()
                logger.info(f"Loaded {len(self._index)} cache entries from index")
            except Exception as e:
                logger.warning(f"Failed to load cache index: {e}")
                self._index = {}
        
        # Cleanup expired entries on startup
        self._cleanup_expired()
    
    def _save_index(self):
        """Persist index to disk"""
        index_file = self.metadata_path / "index.json"
        temp_file = self.metadata_path / "index.json.tmp"
        
        try:
            with open(temp_file, 'w') as f:
                index_data = {k: asdict(v) for k, v in self._index.items()}
                json.dump(index_data, f, indent=2)
            
            # Atomic rename
            temp_file.rename(index_file)
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")
            if temp_file.exists():
                temp_file.unlink()
    
    def compute_cache_key(
        self,
        repo: str,
        commit: str,
        build_strategy: str,
        build_commands: List[str],
        manifest: Dict
    ) -> str:
        """
        Compute content-addressable cache key from build inputs.
        
        The cache key changes when any of these change:
        - Repository URL
        - Commit hash
        - Build strategy
        - Build commands
        - Relevant manifest fields
        
        This ensures cache invalidation when inputs change.
        """
        # Create deterministic input string
        key_components = [
            f"repo:{repo}",
            f"commit:{commit}",
            f"strategy:{build_strategy}",
            f"commands:{','.join(sorted(build_commands))}",
            f"manifest:{json.dumps(manifest, sort_keys=True)}"
        ]
        
        key_string = "|".join(key_components)
        
        # SHA256 hash for content addressing
        cache_key = hashlib.sha256(key_string.encode()).hexdigest()
        
        return cache_key
    
    def compute_manifest_hash(self, manifest: Dict) -> str:
        """Compute hash of manifest for change detection"""
        # Only hash relevant fields for build
        build_relevant = {
            "source": manifest.get("source", {}),
            "build": manifest.get("build", {}),
            "run": manifest.get("run", {}),
            "metadata": manifest.get("metadata", {})
        }
        return hashlib.sha256(
            json.dumps(build_relevant, sort_keys=True).encode()
        ).hexdigest()
    
    def compute_commands_hash(self, build_commands: List[str]) -> str:
        """Compute hash of build commands"""
        return hashlib.sha256(
            "|".join(sorted(build_commands)).encode()
        ).hexdigest()
    
    def get(
        self,
        repo: str,
        commit: str,
        build_strategy: str,
        build_commands: List[str],
        manifest: Dict
    ) -> Optional[CacheEntry]:
        """
        Get cached build result if available.
        
        Returns CacheEntry if cache hit, None if cache miss.
        Updates access time and count on hit.
        """
        cache_key = self.compute_cache_key(
            repo, commit, build_strategy, build_commands, manifest
        )
        
        with self._lock:
            entry = self._index.get(cache_key)
            
            if entry is None:
                self._metrics.misses += 1
                logger.debug(f"Cache MISS for {repo}@{commit}")
                return None
            
            # Check if entry has expired
            created_at = datetime.fromisoformat(entry.created_at)
            if datetime.now() - created_at > timedelta(days=entry.ttl_days):
                logger.info(f"Cache entry expired for {repo}@{commit}")
                self._metrics.misses += 1
                return None
            
            # Cache hit - update access metadata
            entry.last_accessed = datetime.now().isoformat()
            entry.access_count += 1
            self._metrics.hits += 1
            
            logger.info(f"CACHE HIT for {repo}@{commit} (access #{entry.access_count})")
            
            return entry
    
    def put(
        self,
        repo: str,
        commit: str,
        build_strategy: str,
        build_commands: List[str],
        manifest: Dict,
        build_result: Dict,
        artifact_dir: str
    ) -> str:
        """
        Store build result in cache.
        
        Returns the cache key for the stored entry.
        """
        cache_key = self.compute_cache_key(
            repo, commit, build_strategy, build_commands, manifest
        )
        
        with self._lock:
            # Copy artifacts to cache
            artifact_paths = self._store_artifacts(cache_key, artifact_dir)
            
            # Calculate total size
            total_size = sum(
                Path(p).stat().st_size for p in artifact_paths if Path(p).exists()
            )
            
            # Check if we need to make room
            while self._metrics.total_size_bytes + total_size > self.max_size_bytes:
                self._evict_lru()
            
            # Create cache entry
            now = datetime.now().isoformat()
            entry = CacheEntry(
                cache_key=cache_key,
                repo=repo,
                commit=commit,
                build_strategy=build_strategy,
                build_hash=build_result.get("hash", ""),
                artifact_paths=artifact_paths,
                created_at=now,
                last_accessed=now,
                access_count=0,
                manifest_hash=self.compute_manifest_hash(manifest),
                build_commands_hash=self.compute_commands_hash(build_commands),
                size_bytes=total_size,
                ttl_days=self.ttl_days
            )
            
            # Store in index
            self._index[cache_key] = entry
            self._save_index()
            self._update_metrics()
            
            logger.info(f"Cached build for {repo}@{commit} (key: {cache_key[:16]}...)")
            
            return cache_key
    
    def _store_artifacts(self, cache_key: str, source_dir: str) -> List[str]:
        """Copy artifacts to cache storage"""
        # Use first 2 chars of hash for subdirectory
        subdir = cache_key[:2]
        artifact_dir = self.artifacts_path / subdir / cache_key[2:]
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        cached_paths = []
        
        # Copy all files from source directory
        source_path = Path(source_dir)
        if source_path.exists():
            for file_path in source_path.rglob("*"):
                if file_path.is_file():
                    # Preserve directory structure
                    relative_path = file_path.relative_to(source_path)
                    dest_path = artifact_dir / relative_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest_path)
                    cached_paths.append(str(dest_path))
        
        return cached_paths
    
    def get_artifact_dir(self, cache_key: str) -> Optional[Path]:
        """Get the artifact directory for a cache entry"""
        entry = self._index.get(cache_key)
        if entry is None:
            return None
        
        # Artifacts are stored under first 2 chars of hash
        subdir = cache_key[:2]
        artifact_dir = self.artifacts_path / subdir / cache_key[2:]
        
        if artifact_dir.exists():
            return artifact_dir
        
        return None
    
    def invalidate(self, repo: str, commit: Optional[str] = None) -> int:
        """
        Invalidate cache entries for a repository.
        
        If commit is provided, only invalidates that specific commit.
        Otherwise, invalidates all entries for the repository.
        
        Returns the number of entries invalidated.
        """
        with self._lock:
            keys_to_remove = []
            
            for key, entry in self._index.items():
                if entry.repo == repo:
                    if commit is None or entry.commit == commit:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._remove_entry(key)
            
            logger.info(f"Invalidated {len(keys_to_remove)} cache entries for {repo}")
            
            return len(keys_to_remove)
    
    def _remove_entry(self, cache_key: str):
        """Remove a single cache entry"""
        entry = self._index.get(cache_key)
        if entry is None:
            return
        
        # Remove artifact files
        artifact_dir = self.get_artifact_dir(cache_key)
        if artifact_dir and artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        
        # Remove from index
        del self._index[cache_key]
        self._metrics.evictions += 1
        
        logger.debug(f"Removed cache entry {cache_key[:16]}...")
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if not self._index:
            return
        
        # Find entry with oldest last_accessed time
        oldest_key = None
        oldest_time = None
        
        for key, entry in self._index.items():
            access_time = datetime.fromisoformat(entry.last_accessed)
            if oldest_time is None or access_time < oldest_time:
                oldest_time = access_time
                oldest_key = key
        
        if oldest_key:
            self._remove_entry(oldest_key)
            logger.info(f"Evicted LRU entry: {oldest_key[:16]}...")
    
    def _cleanup_expired(self):
        """Remove expired cache entries"""
        now = datetime.now()
        expired_keys = []
        
        for key, entry in self._index.items():
            created_at = datetime.fromisoformat(entry.created_at)
            if now - created_at > timedelta(days=entry.ttl_days):
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_entry(key)
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_metrics(self) -> CacheMetrics:
        """Get current cache metrics"""
        with self._lock:
            self._update_metrics()
            return self._metrics
    
    def _update_metrics(self):
        """Update cache metrics from current state"""
        self._metrics.entry_count = len(self._index)
        self._metrics.total_size_bytes = sum(
            entry.size_bytes for entry in self._index.values()
        )
        
        if self._index:
            entries_by_created = sorted(
                self._index.values(),
                key=lambda e: e.created_at
            )
            self._metrics.oldest_entry = entries_by_created[0].cache_key
            self._metrics.newest_entry = entries_by_created[-1].cache_key
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            # Remove all artifact directories
            if self.artifacts_path.exists():
                shutil.rmtree(self.artifacts_path)
                self.artifacts_path.mkdir(parents=True, exist_ok=True)
            
            # Clear index
            self._index = {}
            self._save_index()
            self._update_metrics()
            
            logger.info("Cache cleared")
    
    def list_entries(self) -> List[Dict]:
        """List all cache entries with metadata"""
        with self._lock:
            entries = []
            for entry in self._index.values():
                entries.append({
                    "cache_key": entry.cache_key[:16] + "...",
                    "repo": entry.repo,
                    "commit": entry.commit,
                    "created_at": entry.created_at,
                    "last_accessed": entry.last_accessed,
                    "access_count": entry.access_count,
                    "size_mb": round(entry.size_bytes / (1024 * 1024), 2),
                    "ttl_days_remaining": self._get_ttl_remaining(entry)
                })
            return sorted(entries, key=lambda e: e["last_accessed"], reverse=True)
    
    def _get_ttl_remaining(self, entry: CacheEntry) -> int:
        """Get remaining TTL in days for an entry"""
        created_at = datetime.fromisoformat(entry.created_at)
        expires_at = created_at + timedelta(days=entry.ttl_days)
        remaining = expires_at - datetime.now()
        return max(0, remaining.days)


# Global cache instance
_build_cache: Optional[BuildCache] = None
_cache_lock = threading.Lock()


def get_build_cache(
    cache_path: str = "./build_cache",
    ttl_days: int = 30,
    max_size_mb: int = 1000
) -> BuildCache:
    """Get or create the global build cache instance"""
    global _build_cache
    
    with _cache_lock:
        if _build_cache is None:
            _build_cache = BuildCache(cache_path, ttl_days, max_size_mb)
        return _build_cache


def reset_build_cache():
    """Reset the global cache instance (for testing)"""
    global _build_cache
    with _cache_lock:
        if _build_cache:
            _build_cache.clear()
        _build_cache = None
