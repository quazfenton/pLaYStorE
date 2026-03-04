from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import os
import logging
from pathlib import Path
from datetime import datetime

from playstorE.core.orchestrator import PlatformOrchestrator
from playstorE.client.github_explorer import GitHubExplorer
from playstorE.storage.workflow_store import WorkflowStore

logger = logging.getLogger(__name__)

app = FastAPI(title="AltStore API", description="Backend API for the Alternative App Store")

# Configure CORS with secure defaults
# Get allowed origins from environment variable (comma-separated for multiple origins)
frontend_urls = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = [url.strip() for url in frontend_urls.split(",") if url.strip()]

# Security: Validate origins to prevent misconfiguration
validated_origins = []
for origin in allowed_origins:
    # Only allow http/https schemes
    if origin.startswith(("http://", "https://")):
        validated_origins.append(origin)
    else:
        logger.warning(f"Invalid CORS origin (must start with http:// or https://): {origin}")

# Fallback to localhost if no valid origins
if not validated_origins:
    validated_origins = ["http://localhost:3000"]
    logger.info("Using default CORS origin: http://localhost:3000")

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
    query: str
    limit: Optional[int] = 20
    filters: Optional[Dict[str, Any]] = None

class InstallRequest(BaseModel):
    github_repo: str
    user_preferences: Optional[Dict[str, Any]] = None

# Store workflow status in memory for demo purposes
# In production, use a database or persistent cache
workflows = {}

@app.get("/")
async def root():
    return {"message": "AltStore API is running", "version": "1.0.0"}

@app.post("/search")
async def search_repos(request: SearchRequest):
    try:
        repos = await orchestrator.github_explorer.search_repos(
            query=request.query,
            filters=request.filters,
            limit=request.limit
        )
        return {"results": [vars(repo) for repo in repos]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze/{owner}/{repo}")
async def analyze_repo(owner: str, repo: str):
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
async def install_app(request: InstallRequest, background_tasks: BackgroundTasks):
    """
    Install an application from GitHub repository.
    
    Returns a workflow ID immediately and processes the installation in the background.
    Use GET /workflow/{workflow_id} to check status.
    """
    # Validate github_repo format
    repo = request.github_repo.strip()
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
    background_tasks.add_task(run_installation, workflow_id, repo, request.user_preferences)
    
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
