"""Action logging utilities for execution tracking.

This module provides comprehensive logging for all execution actions (both direct
and plan-based). All actions are logged to the vm_actions table with full metadata
for audit trails, compliance, and cost tracking.

Usage:
    from dfo.execute.action_logger import ActionLogger, ActionLog

    logger = ActionLogger()

    # Create log entry
    action_id = logger.create_log_entry(
        action_type="stop",
        vm_name="vm-prod-001",
        resource_group="production-rg",
        executed=False,
        reason="Cost optimization"
    )

    # Update after execution
    logger.update_log_entry(
        action_id=action_id,
        status="completed",
        result_message="VM stopped successfully",
        duration_seconds=12.4
    )

    # Query logs
    actions = logger.query_logs(limit=20, filters={"vm_name": "vm-prod-001"})
"""
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

from dfo.core.config import get_settings
from dfo.db.duck import get_db


@dataclass
class ActionLog:
    """Action log entry.

    Represents a single execution action with full context.
    """
    action_id: str
    plan_id: Optional[str]
    vm_id: Optional[str]
    vm_name: str
    resource_group: str
    action_type: str
    action_status: str
    executed: bool
    execution_time: datetime
    duration_seconds: Optional[float]
    result_message: Optional[str]
    reason: Optional[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        data = asdict(self)
        data['execution_time'] = self.execution_time.isoformat()
        return data


class ActionLogger:
    """Manages action logging for executions.

    Handles creation, updating, and querying of execution logs.
    All actions (dry-run and live) are logged with full metadata.
    """

    def __init__(self):
        """Initialize ActionLogger."""
        self.settings = get_settings()
        self.db_manager = get_db()
        self.db = self.db_manager.get_connection()

    def create_log_entry(
        self,
        action_type: str,
        vm_name: str,
        resource_group: str,
        executed: bool,
        source: str = "direct_execution",
        vm_id: Optional[str] = None,
        reason: Optional[str] = None,
        command: Optional[str] = None,
        pre_state: Optional[Dict] = None,
    ) -> str:
        """Create initial log entry.

        Args:
            action_type: Action to perform (stop, deallocate, delete, downsize, restart)
            vm_name: Name of the VM
            resource_group: Resource group name
            executed: True for live execution, False for dry-run
            source: Source of execution (direct_execution or plan_execution)
            vm_id: Azure resource ID (optional)
            reason: User-provided reason (optional)
            command: Full command executed (optional, auto-detected if not provided)
            pre_state: Pre-execution state snapshot (optional)

        Returns:
            str: Generated action ID

        Example:
            >>> logger = ActionLogger()
            >>> action_id = logger.create_log_entry(
            ...     action_type="stop",
            ...     vm_name="vm-prod-001",
            ...     resource_group="production-rg",
            ...     executed=False,
            ...     reason="Cost optimization Q4"
            ... )
            >>> print(action_id)
            act-20251127-143022
        """
        action_id = self._generate_action_id()
        plan_id = f"direct-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # Build metadata
        metadata = {
            "source": source,
            "command": command or self._get_command_line(),
            "user": self._get_current_user(),
            "service_principal": self._get_service_principal(),
            "azure_subscription": self.settings.azure_subscription_id,
            "environment": self._get_environment(),
            "triggered_by": "manual",
        }

        if pre_state:
            metadata["pre_state"] = pre_state

        # Insert log entry
        query = """
        INSERT INTO vm_actions (
            action_id,
            plan_id,
            vm_id,
            vm_name,
            resource_group,
            action_type,
            action_status,
            executed,
            execution_time,
            reason,
            metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        self.db.execute(query, [
            action_id,
            plan_id,
            vm_id,
            vm_name,
            resource_group,
            action_type,
            "pending",
            executed,
            datetime.utcnow(),
            reason or f"Direct execution: {action_type}",
            json.dumps(metadata)
        ])

        return action_id

    def update_log_entry(
        self,
        action_id: str,
        status: str,
        result_message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        post_state: Optional[Dict] = None,
    ):
        """Update log entry with execution results.

        Args:
            action_id: Action ID to update
            status: New status (executing, completed, failed, rolled_back)
            result_message: Success or error message
            duration_seconds: Execution duration
            post_state: Post-execution state snapshot

        Example:
            >>> logger.update_log_entry(
            ...     action_id="act-20251127-143022",
            ...     status="completed",
            ...     result_message="VM stopped successfully",
            ...     duration_seconds=12.4
            ... )
        """
        # Update core fields
        updates = {
            "action_status": status,
            "result_message": result_message,
            "duration_seconds": duration_seconds,
        }

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys() if updates[k] is not None])
        values = [v for v in updates.values() if v is not None]

        if set_clause:
            query = f"UPDATE vm_actions SET {set_clause} WHERE action_id = ?"
            values.append(action_id)
            self.db.execute(query, values)

        # Update metadata with post_state if provided
        if post_state:
            self._update_metadata(action_id, {"post_state": post_state})

    def query_logs(
        self,
        limit: int = 20,
        filters: Optional[Dict] = None,
    ) -> List[ActionLog]:
        """Query action logs with filters.

        Args:
            limit: Maximum number of results
            filters: Filter dictionary with keys:
                - vm_name: Filter by VM name
                - action_type: Filter by action type
                - source: Filter by source (direct/plan)
                - action_status: Filter by status
                - executed: Filter by executed flag
                - since: Filter by start date
                - until: Filter by end date
                - user: Filter by user

        Returns:
            List of ActionLog objects

        Example:
            >>> logger = ActionLogger()
            >>> # Get all actions for a VM
            >>> actions = logger.query_logs(
            ...     limit=10,
            ...     filters={"vm_name": "vm-prod-001"}
            ... )
            >>> # Get only direct executions
            >>> direct_actions = logger.query_logs(
            ...     filters={"source": "direct"}
            ... )
        """
        query = "SELECT * FROM vm_actions WHERE 1=1"
        params = []

        if filters:
            if 'vm_name' in filters:
                query += " AND vm_name = ?"
                params.append(filters['vm_name'])

            if 'action_type' in filters:
                query += " AND action_type = ?"
                params.append(filters['action_type'])

            if 'source' in filters:
                source_filter = 'direct_execution' if filters['source'] == 'direct' else 'plan_execution'
                query += " AND json_extract_string(metadata, '$.source') = ?"
                params.append(source_filter)

            if 'action_status' in filters:
                query += " AND action_status = ?"
                params.append(filters['action_status'])

            if 'executed' in filters:
                query += " AND executed = ?"
                params.append(filters['executed'])

            if 'since' in filters:
                query += " AND execution_time >= ?"
                params.append(filters['since'])

            if 'until' in filters:
                query += " AND execution_time <= ?"
                params.append(filters['until'])

            if 'user' in filters:
                query += " AND json_extract_string(metadata, '$.user') = ?"
                params.append(filters['user'])

        query += " ORDER BY execution_time DESC LIMIT ?"
        params.append(limit)

        # Execute query
        results = self.db.execute(query, params).fetchall()
        return [self._to_action_log(row) for row in results]

    def get_action(self, action_id: str) -> Optional[ActionLog]:
        """Get specific action by ID.

        Args:
            action_id: Action ID to retrieve

        Returns:
            ActionLog object or None if not found

        Example:
            >>> logger = ActionLogger()
            >>> action = logger.get_action("act-20251127-143022")
            >>> if action:
            ...     print(f"Status: {action.action_status}")
        """
        query = "SELECT * FROM vm_actions WHERE action_id = ?"
        result = self.db.execute(query, [action_id]).fetchone()
        return self._to_action_log(result) if result else None

    def get_logs_summary(self, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Get summary statistics for logs.

        Args:
            filters: Same filters as query_logs

        Returns:
            Dictionary with summary statistics

        Example:
            >>> logger = ActionLogger()
            >>> summary = logger.get_logs_summary()
            >>> print(f"Total actions: {summary['total_actions']}")
            >>> print(f"Live executions: {summary['live_executions']}")
        """
        query = "SELECT COUNT(*) as total, SUM(CASE WHEN executed THEN 1 ELSE 0 END) as live FROM vm_actions WHERE 1=1"
        params = []

        # Apply same filters as query_logs
        if filters:
            if 'vm_name' in filters:
                query += " AND vm_name = ?"
                params.append(filters['vm_name'])
            if 'source' in filters:
                source_filter = 'direct_execution' if filters['source'] == 'direct' else 'plan_execution'
                query += " AND json_extract_string(metadata, '$.source') = ?"
                params.append(source_filter)

        result = self.db.execute(query, params).fetchone()

        total = result[0] if result and result[0] is not None else 0
        live = result[1] if result and result[1] is not None else 0

        return {
            "total_actions": total,
            "live_executions": live,
            "dry_run_simulations": total - live,
        }

    def _generate_action_id(self) -> str:
        """Generate unique action ID.

        Format: act-YYYYMMDD-HHMMSS-mmmmmm (includes microseconds for uniqueness)

        Returns:
            Unique action ID
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f')
        return f"act-{timestamp}"

    def _get_command_line(self) -> str:
        """Get the full command line that was executed.

        Returns:
            Full command string
        """
        return ' '.join(sys.argv)

    def _get_current_user(self) -> str:
        """Get current user executing the command.

        Returns:
            Username or 'unknown'
        """
        return os.getenv('USER') or os.getenv('USERNAME') or 'unknown'

    def _get_service_principal(self) -> str:
        """Get service principal name from environment.

        Returns:
            Service principal client ID
        """
        return self.settings.azure_client_id

    def _get_environment(self) -> str:
        """Detect environment type.

        Returns:
            Environment name (production, staging, development, etc.)
        """
        env = os.getenv('DFO_ENVIRONMENT', 'unknown')
        if env == 'unknown':
            # Try to infer from subscription or other settings
            if 'prod' in self.settings.azure_subscription_id.lower():
                return 'production'
            elif 'dev' in self.settings.azure_subscription_id.lower():
                return 'development'
            elif 'stage' in self.settings.azure_subscription_id.lower() or 'stg' in self.settings.azure_subscription_id.lower():
                return 'staging'
        return env

    def _update_metadata(self, action_id: str, updates: Dict):
        """Update metadata JSON field.

        Args:
            action_id: Action ID to update
            updates: Dictionary of metadata updates to merge
        """
        # Get current metadata
        query = "SELECT metadata FROM vm_actions WHERE action_id = ?"
        result = self.db.execute(query, [action_id]).fetchone()

        if result and result[0]:
            metadata = json.loads(result[0])
            metadata.update(updates)

            # Update metadata
            update_query = "UPDATE vm_actions SET metadata = ? WHERE action_id = ?"
            self.db.execute(update_query, [json.dumps(metadata), action_id])

    def _to_action_log(self, row: tuple) -> ActionLog:
        """Convert database row to ActionLog object.

        Args:
            row: Database row tuple (from SELECT * query)
            Expected column order (from schema.sql):
            0: action_id, 1: plan_id, 2: vm_id, 3: vm_name, 4: resource_group,
            5: action_type, 6: action_status, 7: executed, 8: execution_time,
            9: duration_seconds, 10: result_message, 11: reason, 12: metadata

        Returns:
            ActionLog object
        """
        # Parse metadata JSON (handle empty/null)
        metadata_str = row[12] if row[12] else "{}"
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            metadata = {}

        return ActionLog(
            action_id=row[0],
            plan_id=row[1],
            vm_id=row[2],
            vm_name=row[3],
            resource_group=row[4],
            action_type=row[5],
            action_status=row[6],
            executed=bool(row[7]),
            execution_time=datetime.fromisoformat(row[8]) if isinstance(row[8], str) else row[8],
            duration_seconds=row[9],
            result_message=row[10],
            reason=row[11],
            metadata=metadata
        )
