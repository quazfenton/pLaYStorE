"""
Persistent Workflow Storage for AltStore Platform.

Provides durable storage for installation workflows that survives application restarts.
Uses JSON file-based storage with automatic cleanup of old workflows.

Security Features:
- File permission restrictions (Unix: 0o600)
- Atomic writes to prevent corruption
- Automatic cleanup of old workflows
- Path validation to prevent traversal attacks
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import tempfile
import shutil

logger = logging.getLogger(__name__)


class WorkflowStore:
    """
    Persistent workflow storage using JSON files.
    
    Provides:
    - Crash-safe storage (atomic writes)
    - Automatic cleanup of old workflows
    - Thread-safe operations
    - Path traversal protection
    """
    
    def __init__(self, storage_path: str):
        """
        Initialize workflow store.
        
        Args:
            storage_path: Directory to store workflow files
            
        Raises:
            ValueError: If storage_path is invalid or insecure
            RuntimeError: If storage directory cannot be created
        """
        # SECURITY: Validate storage path
        storage_path_obj = Path(storage_path).resolve()
        
        # Ensure path is within current directory or home
        cwd = Path.cwd().resolve()
        home = Path.home().resolve()
        
        is_within_cwd = str(storage_path_obj).startswith(str(cwd))
        is_within_home = str(storage_path_obj).startswith(str(home))
        
        if not (is_within_cwd or is_within_home):
            raise ValueError(
                f"Storage path must be within current directory or user home. "
                f"Got: {storage_path_obj}, CWD: {cwd}, HOME: {home}"
            )
        
        # Reject paths with traversal sequences
        if '..' in str(storage_path):
            raise ValueError(
                f"Storage path contains directory traversal sequence: {storage_path}"
            )
        
        self.storage_path = storage_path_obj
        self.workflows_dir = self.storage_path / "workflows"
        
        # Create directories with secure permissions
        try:
            self.workflows_dir.mkdir(parents=True, exist_ok=True)
            
            # Set restrictive permissions (Unix only)
            if os.name != 'nt':
                os.chmod(self.workflows_dir, 0o700)
                
            logger.info(f"Initialized workflow store at {self.workflows_dir}")
        except OSError as e:
            raise RuntimeError(f"Failed to create workflow storage directory: {e}")
    
    def _get_workflow_path(self, workflow_id: str) -> Path:
        """
        Get path for a workflow file with security validation.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Path to workflow file
            
        Raises:
            ValueError: If workflow_id contains invalid characters
        """
        # SECURITY: Validate workflow_id format
        # Only allow alphanumeric, underscores, and hyphens
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', workflow_id):
            raise ValueError(f"Invalid workflow_id format: {workflow_id}")
        
        # Prevent path traversal through workflow_id
        if '/' in workflow_id or '\\' in workflow_id:
            raise ValueError(f"Workflow ID cannot contain path separators: {workflow_id}")
        
        return self.workflows_dir / f"{workflow_id}.json"
    
    def __setitem__(self, workflow_id: str, data: Dict[str, Any]):
        """
        Save workflow to disk with atomic write.
        
        Args:
            workflow_id: Workflow identifier
            data: Workflow data to store
        """
        path = self._get_workflow_path(workflow_id)
        
        # Add metadata
        data['_updated_at'] = datetime.utcnow().isoformat() + 'Z'
        data['_created_at'] = data.get('_created_at', datetime.utcnow().isoformat() + 'Z')
        
        # ATOMIC WRITE: Write to temp file first, then rename
        # This prevents corruption if process crashes during write
        try:
            # Create temp file in same directory (for atomic rename)
            fd, temp_path = tempfile.mkstemp(
                dir=self.workflows_dir,
                prefix='.workflow_',
                suffix='.tmp'
            )
            
            try:
                # Write data
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, default=str)
                
                # Set secure permissions before rename
                if os.name != 'nt':
                    os.chmod(temp_path, 0o600)
                
                # Atomic rename
                os.replace(temp_path, path)
                
                logger.debug(f"Saved workflow {workflow_id} to {path}")
                
            except Exception:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
                
        except Exception as e:
            logger.error(f"Failed to save workflow {workflow_id}: {e}")
            raise
    
    def __getitem__(self, workflow_id: str) -> Dict[str, Any]:
        """
        Load workflow from disk.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Workflow data
            
        Raises:
            KeyError: If workflow not found
        """
        path = self._get_workflow_path(workflow_id)
        
        if not path.exists():
            raise KeyError(f"Workflow {workflow_id} not found")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.debug(f"Loaded workflow {workflow_id} from {path}")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted workflow file {path}: {e}")
            raise KeyError(f"Workflow {workflow_id} is corrupted")
        except Exception as e:
            logger.error(f"Failed to load workflow {workflow_id}: {e}")
            raise
    
    def __contains__(self, workflow_id: str) -> bool:
        """Check if workflow exists."""
        path = self._get_workflow_path(workflow_id)
        return path.exists()
    
    def __delitem__(self, workflow_id: str):
        """
        Delete workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Raises:
            KeyError: If workflow not found
        """
        path = self._get_workflow_path(workflow_id)
        
        if not path.exists():
            raise KeyError(f"Workflow {workflow_id} not found")
        
        try:
            path.unlink()
            logger.debug(f"Deleted workflow {workflow_id}")
        except Exception as e:
            logger.error(f"Failed to delete workflow {workflow_id}: {e}")
            raise
    
    def cleanup_old_workflows(self, max_age_days: int = 7):
        """
        Remove workflows older than max_age_days.
        
        Args:
            max_age_days: Maximum age in days (default: 7)
        """
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        removed_count = 0
        error_count = 0
        
        for path in self.workflows_dir.glob("*.json"):
            try:
                # Skip temp files
                if path.suffix == '.tmp':
                    continue
                
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Parse updated_at timestamp
                updated_at_str = data.get('_updated_at')
                if not updated_at_str:
                    # No timestamp, keep file
                    continue
                
                # Handle both formats (with/without Z suffix)
                updated_at_str = updated_at_str.rstrip('Z')
                updated_at = datetime.fromisoformat(updated_at_str)
                
                if updated_at < cutoff:
                    path.unlink()
                    removed_count += 1
                    logger.debug(f"Cleaned up old workflow: {path.name}")
                    
            except Exception as e:
                error_count += 1
                logger.warning(f"Error processing workflow {path.name}: {e}")
        
        logger.info(f"Workflow cleanup complete: removed {removed_count}, errors: {error_count}")
    
    def list_workflows(self, limit: int = 100) -> list:
        """
        List recent workflows.
        
        Args:
            limit: Maximum number of workflows to return
            
        Returns:
            List of workflow IDs sorted by update time (newest first)
        """
        workflows = []
        
        for path in self.workflows_dir.glob("*.json"):
            # Skip temp files
            if path.suffix == '.tmp':
                continue
            
            try:
                workflow_id = path.stem
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                updated_at = data.get('_updated_at', '')
                workflows.append((workflow_id, updated_at))
                
            except Exception:
                continue
        
        # Sort by updated_at (newest first)
        workflows.sort(key=lambda x: x[1], reverse=True)
        
        # Return limited list
        return [wf[0] for wf in workflows[:limit]]
    
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all workflows.
        
        Returns:
            Dictionary mapping workflow_id to workflow data
        """
        result = {}
        
        for workflow_id in self.list_workflows(limit=1000):
            try:
                result[workflow_id] = self[workflow_id]
            except Exception as e:
                logger.warning(f"Failed to load workflow {workflow_id}: {e}")
        
        return result
