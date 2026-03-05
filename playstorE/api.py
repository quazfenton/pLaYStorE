from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
import asyncio
import os
import logging
import re
from pathlib import Path
from datetime import datetime
import time
import platform
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from playstorE.core.orchestrator import PlatformOrchestrator
from playstorE.client.github_explorer import GitHubExplorer
from playstorE.storage.workflow_store import WorkflowStore
from playstorE.core.security.middleware import setup_security_middleware
from playstorE.core.errors import setup_error_handlers, AltStoreError, ValidationError, SecurityError

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute", "10/second"])

app = FastAPI(title="AltStore API", description="Backend API for the Alternative App Store")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Set up error handlers
setup_error_handlers(app)

# Configure security middleware with CSP and audit logging
security_config = {
    "csp_default_src": ["'self'"],
    "csp_script_src": ["'self'"],  # No inline scripts
    "csp_style_src": ["'self'"],  # No inline styles
    "csp_img_src": ["'self'", "data:", "https:"],
    "csp_font_src": ["'self'"],
    "csp_connect_src": ["'self'", "https://api.github.com"],
    "csp_frame_ancestors": ["'none'"],  # Prevent clickjacking
    "hsts_max_age": 31536000,  # 1 year
    "hsts_include_subdomains": True,
    "hsts_preload": True,
    "audit_log_level": "INFO",
}

# Add security middleware (must be added early in middleware chain)
setup_security_middleware(app, security_config)

# Configure CORS with secure defaults
# Get allowed origins from environment variable (comma-separated for multiple origins)
frontend_urls = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = [url.strip() for url in frontend_urls.split(",") if url.strip()]

# Security: Validate origins to prevent misconfiguration
validated_origins = []
for origin in allowed_origins:
    # SECURITY: NEVER allow wildcard origins - this enables CSRF attacks
    if origin == "*" or origin.startswith("*."):
        logger.error(f"SECURITY ERROR: Wildcard CORS origin not allowed: {origin}. This is a critical security vulnerability.")
        continue
    # Only allow http/https schemes
    if origin.startswith(("http://", "https://")):
        validated_origins.append(origin)
    else:
        logger.warning(f"Invalid CORS origin (must start with http:// or https://): {origin}")

# SECURITY: Fail closed - require explicit origin configuration
if not validated_origins:
    validated_origins = ["http://localhost:3000"]
    logger.warning("No valid CORS origins configured. Using localhost default. SET FRONTEND_URL in production!")

logger.info(f"CORS enabled for origins: {validated_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=validated_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Request-ID"],
    max_age=600,  # Cache preflight for 10 minutes
)

# Initialize workflow persistence
workflow_storage_path = os.getenv("WORKFLOW_STORAGE", "./data/workflows")
try:
    workflows = WorkflowStore(storage_path=workflow_storage_path)
    logger.info(f"Workflow persistence initialized at {workflow_storage_path}")
except Exception as e:
    logger.error(f"Failed to initialize workflow storage: {e}")
    # Fallback to in-memory storage (will lose data on restart)
    workflows = {}
    logger.warning("Using in-memory workflow storage (data will be lost on restart)")

# Global orchestrator instance
orchestrator_storage_path = os.getenv("ALTSTORE_STORAGE", "./data/altstore_storage")
orchestrator = PlatformOrchestrator(storage_path=orchestrator_storage_path)
logger.info(f"Orchestrator initialized with storage at {orchestrator_storage_path}")

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    limit: Optional[int] = Field(default=20, ge=1, le=100, description="Max results to return")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Search filters")

    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        # Prevent SQL injection patterns
        sql_patterns = ['--', ';', 'DROP ', 'SELECT ', 'UNION ', 'INSERT ', 'DELETE ', 'UPDATE ']
        for pattern in sql_patterns:
            if pattern.lower() in v.lower():
                raise ValueError(f'Invalid query pattern detected: {pattern}')
        return v.strip()

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v):
        if v is None:
            return 20
        return max(1, min(v, 100))


class InstallRequest(BaseModel):
    github_repo: str = Field(..., min_length=3, max_length=200, description="GitHub repository in format owner/name")
    user_preferences: Optional[Dict[str, Any]] = Field(default=None, description="User preferences")

    @field_validator('github_repo')
    @classmethod
    def validate_github_repo(cls, v):
        if not v or not v.strip():
            raise ValueError('Repository name cannot be empty')
        v = v.strip()
        # Validate GitHub repository format: owner/name
        pattern = r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+$'
        if not re.match(pattern, v):
            raise ValueError('Invalid repository format. Expected: owner/name (e.g., torvalds/linux)')
        # Prevent path traversal
        if '..' in v or v.startswith('/') or v.startswith('\\'):
            raise ValueError('Invalid repository name: path traversal not allowed')
        return v

# Store workflow status in memory for demo purposes
# In production, use a database or persistent cache
workflows = {}

@app.get("/")
async def root():
    return {"message": "AltStore API is running", "version": "1.0.0"}


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint - returns basic health status.
    Used for liveness probes.
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.get("/health/ready", tags=["health"])
async def readiness_check():
    """
    Readiness check endpoint - verifies all dependencies are available.
    Used for readiness probes.
    """
    checks = {
        "orchestrator": orchestrator is not None,
        "workflow_store": workflows is not None,
    }
    
    all_healthy = all(checks.values())
    
    if all_healthy:
        return {
            "status": "ready",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    else:
        failed = [k for k, v in checks.items() if not v]
        raise JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "failed_checks": failed,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )


@app.get("/health/live", tags=["health"])
async def liveness_check():
    """
    Liveness check endpoint - confirms the process is alive.
    Used for Kubernetes liveness probes.
    """
    return {"status": "alive"}

@app.post("/search")
@limiter.limit("100/minute")
async def search_repos(request: Request, search_request: SearchRequest):
    try:
        repos = await orchestrator.github_explorer.search_repos(
            query=search_request.query,
            filters=search_request.filters,
            limit=search_request.limit
        )
        return {"results": [vars(repo) for repo in repos]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze/{owner}/{repo}")
@limiter.limit("30/minute")
async def analyze_repo(request: Request, owner: str, repo: str):
    repo_full_name = f"{owner}/{repo}"
    try:
        analysis = await orchestrator.github_explorer.analyze_repo(repo_full_name)
        return {
            "repo": vars(analysis.repo),
            "repo_type": analysis.repo_type.value,
            "confidence": analysis.confidence,
            "build_strategy": analysis.build_strategy,
            "runtime_type": analysis.runtime_type,
            "ports_detected": analysis.ports_detected,
            "wasm_compatible": analysis.wasm_compatible,
            "is_safe": analysis.is_safe,
            "risk_score": analysis.risk_score,
            "suggested_manifest": analysis.suggested_manifest
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/install")
@limiter.limit("10/minute")
async def install_app(request: Request, install_request: InstallRequest, background_tasks: BackgroundTasks):
    """
    Install an application from GitHub repository.

    Returns a workflow ID immediately and processes the installation in the background.
    Use GET /workflow/{workflow_id} to check status.
    """
    # Validate github_repo format
    repo = install_request.github_repo.strip()
    if '/' not in repo:
        raise HTTPException(status_code=400, detail="Invalid repository format. Expected: owner/name")

    # Generate unique workflow ID
    workflow_id = f"wf_{repo.replace('/', '_')}_{int(asyncio.get_event_loop().time())}"

    # Initialize workflow with created timestamp
    initial_data = {
        "status": "starting",
        "progress": 0,
        "repo": repo,
        "created_at": datetime.utcnow().isoformat() + 'Z'
    }

    # Store workflow (works with both WorkflowStore and dict)
    if hasattr(workflows, '__setitem__'):
        workflows[workflow_id] = initial_data
    else:
        workflows[workflow_id] = initial_data

    # Schedule background installation
    background_tasks.add_task(run_installation, workflow_id, repo, install_request.user_preferences)

    logger.info(f"Started installation workflow {workflow_id} for {repo}")
    return {"workflow_id": workflow_id, "status": "started"}

async def run_installation(workflow_id: str, repo: str, preferences: Optional[Dict]):
    """
    Background task to process installation workflow.
    
    Updates workflow status at each stage.
    """
    try:
        # Update status to in_progress
        if workflow_id in workflows:
            workflow_data = workflows[workflow_id]
            workflow_data["status"] = "in_progress"
            workflow_data["stages"] = workflow_data.get("stages", {})
            workflows[workflow_id] = workflow_data
        
        # Execute installation via orchestrator
        result = await orchestrator.discover_and_install(repo, user_preferences=preferences)
        
        # Update workflow with result
        if workflow_id in workflows:
            workflow_data = workflows[workflow_id]
            workflow_data["status"] = "complete" if result.get("success") else "failed"
            workflow_data["result"] = result
            workflow_data["progress"] = 100
            workflow_data["_updated_at"] = datetime.utcnow().isoformat() + 'Z'
            
            if not result.get("success"):
                workflow_data["error"] = result.get("error", "Unknown error")
            
            workflows[workflow_id] = workflow_data
            
    except Exception as e:
        logger.error(f"Installation workflow {workflow_id} failed: {e}")
        if workflow_id in workflows:
            workflow_data = workflows[workflow_id]
            workflow_data["status"] = "failed"
            workflow_data["error"] = str(e)
            workflow_data["_updated_at"] = datetime.utcnow().isoformat() + 'Z'
            workflows[workflow_id] = workflow_data

@app.get("/workflow/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    """
    Get status of an installation workflow.
    
    Returns workflow status, progress, and result if complete.
    """
    try:
        if workflow_id not in workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        workflow_data = workflows[workflow_id]
        
        # Remove internal metadata from response
        response_data = {
            "workflow_id": workflow_id,
            "status": workflow_data.get("status", "unknown"),
            "progress": workflow_data.get("progress", 0),
            "repo": workflow_data.get("repo", ""),
            "created_at": workflow_data.get("created_at", ""),
            "_updated_at": workflow_data.get("_updated_at", "")
        }
        
        # Include result if available
        if "result" in workflow_data:
            response_data["result"] = workflow_data["result"]
        
        # Include error if failed
        if workflow_data.get("status") == "failed" and "error" in workflow_data:
            response_data["error"] = workflow_data["error"]
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflow: {str(e)}")

@app.get("/apps")
async def list_installed_apps():
    # In a real app, this would query the installation manager
    # For now, we'll return the history from orchestrator
    return {"apps": orchestrator.workflow_history}


@app.get("/cache/metrics", tags=["cache"])
async def get_cache_metrics():
    """
    Get build cache performance metrics.
    
    Returns:
    - hits: Number of cache hits
    - misses: Number of cache misses
    - hit_rate: Cache hit rate (0.0 - 1.0)
    - total_size_mb: Total cache size in MB
    - entry_count: Number of cached builds
    """
    metrics = orchestrator.build_cache.get_metrics()
    return metrics.to_dict()


@app.get("/cache/entries", tags=["cache"])
async def list_cache_entries():
    """
    List all cached builds with metadata.
    
    Returns list of cache entries with:
    - cache_key: Short cache key identifier
    - repo: Repository URL
    - commit: Commit hash
    - created_at: When the build was cached
    - last_accessed: Last access time
    - access_count: Number of times accessed
    - size_mb: Cache entry size in MB
    - ttl_days_remaining: Days until expiration
    """
    entries = orchestrator.build_cache.list_entries()
    return {"entries": entries, "count": len(entries)}


@app.delete("/cache/invalidate/{repo:path}", tags=["cache"])
async def invalidate_cache_entry(repo: str, commit: Optional[str] = None):
    """
    Invalidate cache entries for a repository.
    
    If commit is provided, only invalidates that specific commit.
    Otherwise, invalidates all entries for the repository.
    
    Returns the number of entries invalidated.
    """
    count = orchestrator.build_cache.invalidate(repo, commit)
    return {
        "invalidated": count,
        "repo": repo,
        "commit": commit
    }


@app.delete("/cache/clear", tags=["cache"])
async def clear_cache():
    """
    Clear all cache entries.
    
    WARNING: This removes all cached builds and requires rebuilding from scratch.
    """
    orchestrator.build_cache.clear()
    return {"message": "Cache cleared successfully"}


@app.post("/cache/warm", tags=["cache"])
@limiter.limit("5/minute")
async def warm_cache(request: Request, repo: str, commit: Optional[str] = None):
    """
    Pre-warm cache by building a repository.
    
    This triggers a build and caches the result for future use.
    Useful for pre-building popular repositories during off-peak hours.
    """
    try:
        # Analyze repo first
        analysis = await orchestrator.github_explorer.analyze_repo(repo)
        if not analysis or not analysis.is_safe:
            raise HTTPException(status_code=400, detail="Repository analysis failed")
        
        manifest = analysis.suggested_manifest
        if commit:
            manifest["source"]["commit"] = commit
        
        # Build and cache
        build_result = await orchestrator._stage_build(manifest)
        
        if build_result and build_result.get("cached"):
            return {
                "status": "cached",
                "repo": repo,
                "cache_key": build_result.get("cache_key"),
                "message": "Build retrieved from cache"
            }
        else:
            return {
                "status": "built",
                "repo": repo,
                "build_hash": build_result.get("hash") if build_result else None,
                "message": "Build completed and cached"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
