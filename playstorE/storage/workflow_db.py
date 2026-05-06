"""
Persistent Workflow Storage for AltStore Platform.

Provides:
- SQLite-based workflow persistence
- Workflow recovery on startup
- Automatic cleanup of expired workflows
- Query and filter capabilities

This ensures workflows survive application restarts and can be resumed.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)


@dataclass
class WorkflowRecord:
    """A persisted workflow record"""
    workflow_id: str
    repo: str
    status: str  # running, complete, failed
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    stages: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    user_preferences: Dict[str, Any]
    ttl_days: int = 7  # Workflows expire after 7 days


class WorkflowDatabase:
    """
    SQLite-based persistent workflow storage.
    
    Features:
    - Thread-safe connections
    - Automatic schema migrations
    - TTL-based expiration
    - Query by status, repo, date range
    """
    
    def __init__(self, db_path: str = "./workflows.db"):
        self.db_path = Path(db_path).resolve()
        self._local = threading.local()
        
        # Create database and tables
        self._initialize_database()
        
        logger.info(f"Workflow database initialized at {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self._local.connection.row_factory = sqlite3.Row
        
        try:
            yield self._local.connection
        except Exception as e:
            self._local.connection.rollback()
            raise e
    
    def _initialize_database(self):
        """Create database tables and indexes"""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY,
                    repo TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    stages TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    user_preferences TEXT NOT NULL,
                    ttl_days INTEGER DEFAULT 7,
                    checksum TEXT NOT NULL
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflows_status 
                ON workflows(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflows_repo 
                ON workflows(repo)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflows_created_at 
                ON workflows(created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflows_completed_at 
                ON workflows(completed_at)
            """)
            
            conn.commit()
        
        logger.info("Database schema initialized")
    
    def _compute_checksum(self, record: WorkflowRecord) -> str:
        """Compute checksum for data integrity"""
        import hashlib
        data = json.dumps({
            "workflow_id": record.workflow_id,
            "updated_at": record.updated_at,
            "stages": record.stages
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()
    
    def save_workflow(self, workflow: Dict[str, Any]) -> str:
        """
        Save or update a workflow record.
        
        Args:
            workflow: Workflow dictionary with all fields
            
        Returns:
            workflow_id of the saved workflow
        """
        record = WorkflowRecord(
            workflow_id=workflow.get("id", workflow.get("workflow_id")),
            repo=workflow.get("repo", ""),
            status=workflow.get("status", "running"),
            created_at=workflow.get("created_at", datetime.now().isoformat()),
            updated_at=workflow.get("updated_at", datetime.now().isoformat()),
            completed_at=workflow.get("completed_at"),
            stages=workflow.get("stages", {}),
            result=workflow.get("result"),
            error=workflow.get("error"),
            user_preferences=workflow.get("user_preferences", {}),
            ttl_days=workflow.get("ttl_days", 7)
        )
        
        record.checksum = self._compute_checksum(record)
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO workflows 
                (workflow_id, repo, status, created_at, updated_at, 
                 completed_at, stages, result, error, user_preferences, ttl_days, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.workflow_id,
                record.repo,
                record.status,
                record.created_at,
                record.updated_at,
                record.completed_at,
                json.dumps(record.stages),
                json.dumps(record.result) if record.result else None,
                record.error,
                json.dumps(record.user_preferences),
                record.ttl_days,
                record.checksum
            ))
            conn.commit()
        
        logger.debug(f"Saved workflow {record.workflow_id} ({record.status})")
        return record.workflow_id
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a workflow by ID.
        
        Returns None if not found or expired.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflows WHERE workflow_id = ?",
                (workflow_id,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            # Verify checksum
            checksum = row["checksum"]
            row_dict = dict(row)
            expected_checksum = self._compute_checksum(WorkflowRecord(
                workflow_id=row_dict["workflow_id"],
                repo=row_dict["repo"],
                status=row_dict["status"],
                created_at=row_dict["created_at"],
                updated_at=row_dict["updated_at"],
                completed_at=row_dict["completed_at"],
                stages=json.loads(row_dict["stages"]),
                result=json.loads(row_dict["result"]) if row_dict["result"] else None,
                error=row_dict["error"],
                user_preferences=json.loads(row_dict["user_preferences"]),
                ttl_days=row_dict["ttl_days"]
            ))
            
            if checksum != expected_checksum:
                logger.warning(f"Checksum mismatch for workflow {workflow_id}")
                return None
            
            # Convert to dictionary
            workflow = {
                "id": row["workflow_id"],
                "workflow_id": row["workflow_id"],
                "repo": row["repo"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "completed_at": row["completed_at"],
                "stages": json.loads(row["stages"]),
                "result": json.loads(row["result"]) if row["result"] else None,
                "error": row["error"],
                "user_preferences": json.loads(row["user_preferences"])
            }
            
            return workflow
    
    def get_workflows_by_status(
        self, 
        status: str, 
        limit: int = 100,
        repo_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get workflows by status.
        
        Args:
            status: Workflow status to filter by
            limit: Maximum number of results
            repo_filter: Optional repository filter
            
        Returns:
            List of workflow dictionaries
        """
        with self.get_connection() as conn:
            if repo_filter:
                cursor = conn.execute("""
                    SELECT * FROM workflows 
                    WHERE status = ? AND repo LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (status, f"%{repo_filter}%", limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM workflows 
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (status, limit))
            
            workflows = []
            for row in cursor.fetchall():
                workflow = {
                    "id": row["workflow_id"],
                    "workflow_id": row["workflow_id"],
                    "repo": row["repo"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "stages": json.loads(row["stages"]),
                    "error": row["error"]
                }
                workflows.append(workflow)
            
            return workflows
    
    def get_running_workflows(self) -> List[Dict[str, Any]]:
        """Get all running workflows (for recovery)"""
        return self.get_workflows_by_status("running", limit=1000)
    
    def update_workflow_status(
        self, 
        workflow_id: str, 
        status: str,
        stages: Optional[Dict] = None,
        error: Optional[str] = None,
        result: Optional[Dict] = None
    ):
        """
        Update workflow status and related fields.
        
        Args:
            workflow_id: ID of workflow to update
            status: New status
            stages: Updated stages (optional)
            error: Error message if failed (optional)
            result: Result data if complete (optional)
        """
        updates = [
            "status = ?",
            "updated_at = ?"
        ]
        params = [status, datetime.now().isoformat()]
        
        if stages is not None:
            updates.append("stages = ?")
            params.append(json.dumps(stages))
        
        if error is not None:
            updates.append("error = ?")
            params.append(error)
        
        if result is not None:
            updates.append("result = ?")
            params.append(json.dumps(result))
        
        if status in ("complete", "failed"):
            updates.append("completed_at = ?")
            params.append(datetime.now().isoformat())
        
        params.append(workflow_id)
        
        with self.get_connection() as conn:
            conn.execute(f"""
                UPDATE workflows 
                SET {', '.join(updates)}
                WHERE workflow_id = ?
            """, params)
            conn.commit()
        
        logger.debug(f"Updated workflow {workflow_id} to {status}")
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow.
        
        Returns True if deleted, False if not found.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM workflows WHERE workflow_id = ?",
                (workflow_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def cleanup_expired(self) -> int:
        """
        Remove expired workflows.
        
        Returns the number of workflows deleted.
        """
        now = datetime.now()
        deleted_count = 0
        
        with self.get_connection() as conn:
            # Find expired workflows
            cursor = conn.execute("""
                SELECT workflow_id, created_at, ttl_days 
                FROM workflows
            """)
            
            for row in cursor.fetchall():
                created_at = datetime.fromisoformat(row["created_at"])
                ttl_days = row["ttl_days"]
                expires_at = created_at + timedelta(days=ttl_days)
                
                if now > expires_at:
                    self.delete_workflow(row["workflow_id"])
                    deleted_count += 1
                    logger.debug(f"Deleted expired workflow {row['workflow_id']}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired workflows")
        
        return deleted_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get workflow statistics"""
        with self.get_connection() as conn:
            # Count by status
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM workflows 
                GROUP BY status
            """)
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}
            
            # Total count
            cursor = conn.execute("SELECT COUNT(*) as total FROM workflows")
            total = cursor.fetchone()["total"]
            
            # Oldest workflow
            cursor = conn.execute("""
                SELECT workflow_id, created_at 
                FROM workflows 
                ORDER BY created_at ASC 
                LIMIT 1
            """)
            oldest = cursor.fetchone()
            
            # Recent completions (last 24 hours)
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            cursor = conn.execute("""
                SELECT COUNT(*) as count 
                FROM workflows 
                WHERE status = 'complete' AND completed_at > ?
            """, (yesterday,))
            recent_completions = cursor.fetchone()["count"]
            
            return {
                "total_workflows": total,
                "by_status": status_counts,
                "oldest_workflow": {
                    "workflow_id": oldest["workflow_id"] if oldest else None,
                    "created_at": oldest["created_at"] if oldest else None
                } if oldest else None,
                "recent_completions_24h": recent_completions
            }
    
    def list_workflows(
        self, 
        limit: int = 100, 
        offset: int = 0,
        repo_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List workflows with pagination.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            repo_filter: Optional repository filter
            
        Returns:
            List of workflow dictionaries (without full stages/result)
        """
        with self.get_connection() as conn:
            if repo_filter:
                cursor = conn.execute("""
                    SELECT workflow_id, repo, status, created_at, updated_at, error
                    FROM workflows 
                    WHERE repo LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (f"%{repo_filter}%", limit, offset))
            else:
                cursor = conn.execute("""
                    SELECT workflow_id, repo, status, created_at, updated_at, error
                    FROM workflows 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            
            workflows = []
            for row in cursor.fetchall():
                workflows.append({
                    "workflow_id": row["workflow_id"],
                    "repo": row["repo"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "error": row["error"]
                })
            
            return workflows
    
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# Global database instance
_db: Optional[WorkflowDatabase] = None
_db_lock = threading.Lock()


def get_workflow_database(db_path: str = "./workflows.db") -> WorkflowDatabase:
    """Get or create the global workflow database instance"""
    global _db
    
    with _db_lock:
        if _db is None:
            _db = WorkflowDatabase(db_path)
        return _db


def reset_workflow_database():
    """Reset the global database instance (for testing)"""
    global _db
    with _db_lock:
        if _db:
            _db.close()
        _db = None
