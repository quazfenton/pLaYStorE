from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import os
from pathlib import Path

from playstorE.core.orchestrator import PlatformOrchestrator
from playstorE.client.github_explorer import GitHubExplorer

app = FastAPI(title="AltStore API", description="Backend API for the Alternative App Store")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
orchestrator = PlatformOrchestrator(storage_path="./data/altstore_storage")

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
    # This will be a long-running process, so we run it in the background
    # and return a workflow ID immediately
    workflow_id = f"wf_{request.github_repo.replace('/', '_')}_{int(asyncio.get_event_loop().time())}"
    workflows[workflow_id] = {"status": "starting", "progress": 0, "repo": request.github_repo}
    
    background_tasks.add_task(run_installation, workflow_id, request.github_repo, request.user_preferences)
    
    return {"workflow_id": workflow_id, "status": "started"}

async def run_installation(workflow_id: str, repo: str, preferences: Optional[Dict]):
    try:
        workflows[workflow_id]["status"] = "in_progress"
        # The orchestrator already handles the full workflow
        result = await orchestrator.discover_and_install(repo, user_preferences=preferences)
        workflows[workflow_id]["status"] = "complete" if result.get("success") else "failed"
        workflows[workflow_id]["result"] = result
        if not result.get("success"):
            workflows[workflow_id]["error"] = result.get("error")
    except Exception as e:
        workflows[workflow_id]["status"] = "failed"
        workflows[workflow_id]["error"] = str(e)

@app.get("/workflow/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflows[workflow_id]

@app.get("/apps")
async def list_installed_apps():
    # In a real app, this would query the installation manager
    # For now, we'll return the history from orchestrator
    return {"apps": orchestrator.workflow_history}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
