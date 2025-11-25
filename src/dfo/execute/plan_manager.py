"""Plan manager for CRUD operations on execution plans."""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import duckdb

from dfo.core.config import get_settings
from dfo.db.duck import get_db
from dfo.execute.models import (
    ActionHistory,
    ActionStatus,
    ActionType,
    CreatePlanRequest,
    EventType,
    ExecutionPlan,
    PlanAction,
    PlanStatus,
    Severity,
)


def generate_plan_id() -> str:
    """Generate a unique plan ID."""
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"plan-{timestamp}-{datetime.now().microsecond:06d}"[:20]


def generate_action_id() -> str:
    """Generate a unique action ID."""
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"action-{timestamp}-{datetime.now().microsecond:06d}"[:24]


def generate_history_id() -> str:
    """Generate a unique history ID."""
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"hist-{timestamp}-{datetime.now().microsecond:06d}"[:22]


class PlanManager:
    """Manages execution plans in DuckDB."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize plan manager.

        Args:
            db_path: Path to DuckDB file (defaults to config setting)
        """
        self.db_path = db_path or get_settings().dfo_duckdb_file
        self.conn = get_db().get_connection()

    # ========================================================================
    # PLAN CRUD OPERATIONS
    # ========================================================================

    def create_plan(self, request: CreatePlanRequest) -> ExecutionPlan:
        """Create a new execution plan.

        Args:
            request: Plan creation request

        Returns:
            Created execution plan

        Raises:
            ValueError: If analysis results not found
        """
        # Generate plan ID
        plan_id = generate_plan_id()

        # Calculate TTL
        settings = get_settings()
        ttl_days = getattr(settings, 'plan_ttl_days', 30)
        expires_at = datetime.now() + timedelta(days=ttl_days)

        # Create plan object
        plan = ExecutionPlan(
            plan_id=plan_id,
            plan_name=request.plan_name,
            description=request.description,
            created_at=datetime.now(),
            created_by=request.created_by,
            status=PlanStatus.DRAFT,
            analysis_types=request.analysis_types,
            severity_filter=request.severity_filter,
            expires_at=expires_at,
            tags=request.tags,
        )

        # Insert into database
        self.conn.execute(
            """
            INSERT INTO execution_plans (
                plan_id, plan_name, description, created_at, created_by,
                status, analysis_types, severity_filter, total_actions,
                total_estimated_savings, expires_at, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                plan.plan_id,
                plan.plan_name,
                plan.description,
                plan.created_at,
                plan.created_by,
                plan.status,  # Already a string due to use_enum_values = True
                json.dumps(plan.analysis_types),
                plan.severity_filter,
                0,  # Will be updated when actions are added
                0.0,  # Will be updated when actions are added
                plan.expires_at,
                json.dumps(plan.tags) if plan.tags else None,
            ],
        )

        # Fetch analysis results and create actions
        actions = self._create_actions_from_analysis(
            plan_id, request.analysis_types, request.severity_filter, request.limit
        )

        # Update plan metrics
        total_savings = sum(a.estimated_monthly_savings for a in actions)
        self.conn.execute(
            """
            UPDATE execution_plans
            SET total_actions = ?, total_estimated_savings = ?
            WHERE plan_id = ?
            """,
            [len(actions), total_savings, plan_id],
        )

        # Reload plan with updated metrics
        return self.get_plan(plan_id)

    def get_plan(self, plan_id: str) -> ExecutionPlan:
        """Get execution plan by ID.

        Args:
            plan_id: Plan ID

        Returns:
            Execution plan

        Raises:
            ValueError: If plan not found
        """
        result = self.conn.execute(
            "SELECT * FROM execution_plans WHERE plan_id = ?", [plan_id]
        ).fetchone()

        if not result:
            raise ValueError(f"Plan not found: {plan_id}")

        return self._row_to_plan(result)

    def list_plans(
        self,
        status: Optional[PlanStatus] = None,
        limit: Optional[int] = None,
        sort_by: str = "created_at",
    ) -> List[ExecutionPlan]:
        """List execution plans.

        Args:
            status: Filter by status
            limit: Maximum number of plans to return
            sort_by: Sort field (created_at, total_estimated_savings)

        Returns:
            List of execution plans
        """
        query = "SELECT * FROM execution_plans"
        params = []

        if status:
            query += " WHERE status = ?"
            params.append(status.value)

        # Validate sort_by to prevent SQL injection
        valid_sorts = ["created_at", "total_estimated_savings", "plan_name"]
        if sort_by not in valid_sorts:
            sort_by = "created_at"

        query += f" ORDER BY {sort_by} DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        results = self.conn.execute(query, params).fetchall()
        return [self._row_to_plan(row) for row in results]

    def update_plan_status(
        self, plan_id: str, new_status: PlanStatus, **kwargs
    ) -> ExecutionPlan:
        """Update plan status.

        Args:
            plan_id: Plan ID
            new_status: New status
            **kwargs: Additional fields to update

        Returns:
            Updated execution plan
        """
        # Build update query
        updates = ["status = ?"]
        params = [new_status.value]

        # Add timestamp fields based on status
        if new_status == PlanStatus.VALIDATED:
            updates.append("validated_at = ?")
            params.append(datetime.now())
        elif new_status == PlanStatus.APPROVED:
            updates.append("approved_at = ?")
            params.append(datetime.now())
            if "approved_by" in kwargs:
                updates.append("approved_by = ?")
                params.append(kwargs["approved_by"])
        elif new_status == PlanStatus.EXECUTING:
            updates.append("executed_at = ?")
            params.append(datetime.now())
        elif new_status in [PlanStatus.COMPLETED, PlanStatus.FAILED]:
            updates.append("completed_at = ?")
            params.append(datetime.now())

        # Add validation errors/warnings if provided
        if "validation_errors" in kwargs:
            updates.append("validation_errors = ?")
            params.append(json.dumps(kwargs["validation_errors"]))
        if "validation_warnings" in kwargs:
            updates.append("validation_warnings = ?")
            params.append(json.dumps(kwargs["validation_warnings"]))

        params.append(plan_id)
        query = f"UPDATE execution_plans SET {', '.join(updates)} WHERE plan_id = ?"

        self.conn.execute(query, params)
        return self.get_plan(plan_id)

    def delete_plan(self, plan_id: str) -> None:
        """Delete execution plan.

        Args:
            plan_id: Plan ID

        Raises:
            ValueError: If plan cannot be deleted (not in draft/validated status)
        """
        plan = self.get_plan(plan_id)

        # Only allow deletion of draft or validated plans
        if plan.status not in [PlanStatus.DRAFT, PlanStatus.VALIDATED]:
            raise ValueError(
                f"Cannot delete plan in {plan.status} status. "
                "Only draft or validated plans can be deleted."
            )

        # Delete actions first (due to foreign key constraint)
        self.conn.execute("DELETE FROM action_history WHERE plan_id = ?", [plan_id])
        self.conn.execute("DELETE FROM plan_actions WHERE plan_id = ?", [plan_id])
        self.conn.execute("DELETE FROM execution_plans WHERE plan_id = ?", [plan_id])

    # ========================================================================
    # ACTION OPERATIONS
    # ========================================================================

    def get_actions(self, plan_id: str) -> List[PlanAction]:
        """Get all actions for a plan.

        Args:
            plan_id: Plan ID

        Returns:
            List of plan actions
        """
        results = self.conn.execute(
            "SELECT * FROM plan_actions WHERE plan_id = ? ORDER BY execution_order",
            [plan_id],
        ).fetchall()

        return [self._row_to_action(row) for row in results]

    def get_action(self, action_id: str) -> PlanAction:
        """Get action by ID.

        Args:
            action_id: Action ID

        Returns:
            Plan action

        Raises:
            ValueError: If action not found
        """
        result = self.conn.execute(
            "SELECT * FROM plan_actions WHERE action_id = ?", [action_id]
        ).fetchone()

        if not result:
            raise ValueError(f"Action not found: {action_id}")

        return self._row_to_action(result)

    def update_action_status(
        self, action_id: str, new_status: ActionStatus, **kwargs
    ) -> PlanAction:
        """Update action status.

        Args:
            action_id: Action ID
            new_status: New status
            **kwargs: Additional fields to update

        Returns:
            Updated plan action
        """
        # Get current action for history
        current = self.get_action(action_id)

        # Build update query
        updates = ["status = ?"]
        params = [new_status.value]

        # Add timestamp fields based on status
        if new_status == ActionStatus.VALIDATED:
            updates.append("validated_at = ?")
            params.append(datetime.now())
        elif new_status == ActionStatus.RUNNING:
            updates.append("execution_started_at = ?")
            params.append(datetime.now())
        elif new_status in [ActionStatus.COMPLETED, ActionStatus.FAILED]:
            updates.append("execution_completed_at = ?")
            params.append(datetime.now())

            # Calculate duration
            if current.execution_started_at:
                duration = int((datetime.now() - current.execution_started_at).total_seconds())
                updates.append("execution_duration_seconds = ?")
                params.append(duration)

        # Add optional fields
        for field in [
            "validation_status",
            "validation_details",
            "execution_result",
            "execution_details",
            "error_message",
            "error_code",
            "realized_monthly_savings",
        ]:
            if field in kwargs:
                updates.append(f"{field} = ?")
                value = kwargs[field]
                if field in ["validation_details", "execution_details"] and isinstance(
                    value, dict
                ):
                    value = json.dumps(value)
                params.append(value)

        params.append(action_id)
        query = f"UPDATE plan_actions SET {', '.join(updates)} WHERE action_id = ?"

        self.conn.execute(query, params)

        # Log to history
        self._log_action_history(
            action_id,
            current.plan_id,
            EventType.COMPLETED if new_status == ActionStatus.COMPLETED else EventType.FAILED
            if new_status == ActionStatus.FAILED
            else EventType.EXECUTING,
            current.status.value,
            new_status.value,
            kwargs.get("details"),
        )

        return self.get_action(action_id)

    def add_action(
        self,
        plan_id: str,
        resource_id: str,
        resource_name: str,
        analysis_type: str,
        action_type: ActionType,
        estimated_monthly_savings: float,
        **kwargs,
    ) -> PlanAction:
        """Add action to plan.

        Args:
            plan_id: Plan ID
            resource_id: Resource ID
            resource_name: Resource name
            analysis_type: Analysis type
            action_type: Action type
            estimated_monthly_savings: Estimated savings
            **kwargs: Additional action fields

        Returns:
            Created plan action

        Raises:
            ValueError: If plan not in draft status
        """
        plan = self.get_plan(plan_id)
        if plan.status != PlanStatus.DRAFT:
            raise ValueError(f"Cannot add actions to plan in {plan.status} status")

        action_id = generate_action_id()

        # Get next execution order
        result = self.conn.execute(
            "SELECT MAX(execution_order) FROM plan_actions WHERE plan_id = ?",
            [plan_id],
        ).fetchone()
        execution_order = (result[0] or 0) + 1

        # Determine if action is rollback-capable
        rollback_possible = action_type in [ActionType.STOP, ActionType.DEALLOCATE]

        action = PlanAction(
            action_id=action_id,
            plan_id=plan_id,
            resource_id=resource_id,
            resource_name=resource_name,
            resource_type=kwargs.get("resource_type", "vm"),
            resource_group=kwargs.get("resource_group"),
            location=kwargs.get("location"),
            subscription_id=kwargs.get("subscription_id"),
            analysis_id=kwargs.get("analysis_id"),
            analysis_type=analysis_type,
            severity=kwargs.get("severity"),
            action_type=action_type,
            action_params=kwargs.get("action_params"),
            estimated_monthly_savings=estimated_monthly_savings,
            execution_order=execution_order,
            rollback_possible=rollback_possible,
        )

        self._insert_action(action)

        # Update plan metrics
        self._update_plan_metrics(plan_id)

        return action

    def remove_action(self, action_id: str) -> None:
        """Remove action from plan.

        Args:
            action_id: Action ID

        Raises:
            ValueError: If plan not in draft status
        """
        action = self.get_action(action_id)
        plan = self.get_plan(action.plan_id)

        if plan.status != PlanStatus.DRAFT:
            raise ValueError(f"Cannot remove actions from plan in {plan.status} status")

        self.conn.execute("DELETE FROM action_history WHERE action_id = ?", [action_id])
        self.conn.execute("DELETE FROM plan_actions WHERE action_id = ?", [action_id])

        # Update plan metrics
        self._update_plan_metrics(action.plan_id)

    # ========================================================================
    # HISTORY OPERATIONS
    # ========================================================================

    def get_action_history(self, action_id: str) -> List[ActionHistory]:
        """Get history for an action.

        Args:
            action_id: Action ID

        Returns:
            List of history entries
        """
        results = self.conn.execute(
            "SELECT * FROM action_history WHERE action_id = ? ORDER BY timestamp",
            [action_id],
        ).fetchall()

        return [self._row_to_history(row) for row in results]

    def get_plan_history(self, plan_id: str) -> List[ActionHistory]:
        """Get all history for a plan.

        Args:
            plan_id: Plan ID

        Returns:
            List of history entries
        """
        results = self.conn.execute(
            "SELECT * FROM action_history WHERE plan_id = ? ORDER BY timestamp",
            [plan_id],
        ).fetchall()

        return [self._row_to_history(row) for row in results]

    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================

    def _create_actions_from_analysis(
        self,
        plan_id: str,
        analysis_types: List[str],
        severity_filter: Optional[str],
        limit: Optional[int],
    ) -> List[PlanAction]:
        """Create actions from analysis results.

        Args:
            plan_id: Plan ID
            analysis_types: List of analysis types
            severity_filter: Severity filter
            limit: Maximum actions to create

        Returns:
            List of created actions
        """
        actions = []
        execution_order = 1

        for analysis_type in analysis_types:
            # Map analysis type to table and action
            table_name, action_type = self._map_analysis_to_action(analysis_type)

            # Build query
            query = f"SELECT * FROM {table_name}"
            params = []

            if severity_filter:
                severities = [s.strip() for s in severity_filter.split(",")]
                placeholders = ",".join(["?"] * len(severities))
                query += f" WHERE severity IN ({placeholders})"
                params.extend(severities)

            query += " ORDER BY estimated_monthly_savings DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            # Fetch results
            result_obj = self.conn.execute(query, params)
            columns = [desc[0] for desc in result_obj.description]
            results = result_obj.fetchall()

            # Create actions
            for row in results:
                action = self._analysis_row_to_action(
                    row, columns, plan_id, analysis_type, action_type, execution_order
                )
                self._insert_action(action)
                actions.append(action)
                execution_order += 1

        return actions

    def _map_analysis_to_action(self, analysis_type: str) -> tuple[str, ActionType]:
        """Map analysis type to table name and action type."""
        mapping = {
            "idle-vms": ("vm_idle_analysis", ActionType.DEALLOCATE),
            "low-cpu": ("vm_low_cpu_analysis", ActionType.DOWNSIZE),
            "stopped-vms": ("vm_stopped_vms_analysis", ActionType.DELETE),
        }

        if analysis_type not in mapping:
            raise ValueError(f"Unknown analysis type: {analysis_type}")

        return mapping[analysis_type]

    def _analysis_row_to_action(
        self,
        row: tuple,
        columns: List[str],
        plan_id: str,
        analysis_type: str,
        action_type: ActionType,
        execution_order: int,
    ) -> PlanAction:
        """Convert analysis row to plan action."""
        data = dict(zip(columns, row))

        action_id = generate_action_id()

        # Determine rollback capability
        rollback_possible = action_type in [ActionType.STOP, ActionType.DEALLOCATE]

        # Build action params for downsize
        action_params = None
        if action_type == ActionType.DOWNSIZE and "recommended_sku" in data:
            action_params = {"new_size": data["recommended_sku"]}

        return PlanAction(
            action_id=action_id,
            plan_id=plan_id,
            resource_id=data["vm_id"],
            resource_name=data["vm_id"].split("/")[-1],  # Extract name from ID
            resource_type="vm",
            analysis_id=data.get("vm_id"),  # Use vm_id as analysis_id
            analysis_type=analysis_type,
            severity=data.get("severity"),
            action_type=action_type,
            action_params=action_params,
            estimated_monthly_savings=data.get("estimated_monthly_savings", 0.0),
            execution_order=execution_order,
            rollback_possible=rollback_possible,
        )

    def _insert_action(self, action: PlanAction) -> None:
        """Insert action into database."""
        self.conn.execute(
            """
            INSERT INTO plan_actions (
                action_id, plan_id, resource_id, resource_name, resource_type,
                resource_group, location, subscription_id, analysis_id, analysis_type,
                severity, action_type, action_params, estimated_monthly_savings,
                status, execution_order, rollback_possible
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                action.action_id,
                action.plan_id,
                action.resource_id,
                action.resource_name,
                action.resource_type,
                action.resource_group,
                action.location,
                action.subscription_id,
                action.analysis_id,
                action.analysis_type,
                action.severity,  # Already a string value
                action.action_type,  # Already a string due to use_enum_values = True
                json.dumps(action.action_params) if action.action_params else None,
                action.estimated_monthly_savings,
                action.status,  # Already a string due to use_enum_values = True
                action.execution_order,
                action.rollback_possible,
            ],
        )

    def _update_plan_metrics(self, plan_id: str) -> None:
        """Update plan metrics from actions."""
        result = self.conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped,
                COALESCE(SUM(estimated_monthly_savings), 0.0) as estimated_savings,
                COALESCE(SUM(realized_monthly_savings), 0.0) as realized_savings
            FROM plan_actions
            WHERE plan_id = ?
            """,
            [plan_id],
        ).fetchone()

        self.conn.execute(
            """
            UPDATE execution_plans
            SET total_actions = ?,
                completed_actions = ?,
                failed_actions = ?,
                skipped_actions = ?,
                total_estimated_savings = ?,
                total_realized_savings = ?
            WHERE plan_id = ?
            """,
            [
                result[0] or 0,
                result[1] or 0,
                result[2] or 0,
                result[3] or 0,
                result[4] or 0.0,
                result[5] or 0.0,
                plan_id,
            ],
        )

    def _log_action_history(
        self,
        action_id: str,
        plan_id: str,
        event_type: EventType,
        previous_status: Optional[str],
        new_status: Optional[str],
        details: Optional[Dict[str, Any]] = None,
        performed_by: str = "system",
    ) -> None:
        """Log action history entry."""
        history_id = generate_history_id()

        self.conn.execute(
            """
            INSERT INTO action_history (
                history_id, action_id, plan_id, timestamp, event_type,
                previous_status, new_status, details, performed_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                history_id,
                action_id,
                plan_id,
                datetime.now(),
                event_type.value,
                previous_status,
                new_status,
                json.dumps(details) if details else None,
                performed_by,
            ],
        )

    def _row_to_plan(self, row: tuple) -> ExecutionPlan:
        """Convert database row to ExecutionPlan."""
        columns = [desc[0] for desc in self.conn.description]
        data = dict(zip(columns, row))

        return ExecutionPlan(
            plan_id=data["plan_id"],
            plan_name=data["plan_name"],
            description=data["description"],
            created_at=data["created_at"],
            created_by=data["created_by"],
            status=PlanStatus(data["status"]),
            validated_at=data.get("validated_at"),
            validation_errors=json.loads(data["validation_errors"])
            if data.get("validation_errors")
            else None,
            validation_warnings=json.loads(data["validation_warnings"])
            if data.get("validation_warnings")
            else None,
            approved_at=data.get("approved_at"),
            approved_by=data.get("approved_by"),
            analysis_types=json.loads(data["analysis_types"])
            if data.get("analysis_types")
            else [],
            severity_filter=data.get("severity_filter"),
            resource_filters=json.loads(data["resource_filters"])
            if data.get("resource_filters")
            else None,
            total_actions=data.get("total_actions") or 0,
            completed_actions=data.get("completed_actions") or 0,
            failed_actions=data.get("failed_actions") or 0,
            skipped_actions=data.get("skipped_actions") or 0,
            total_estimated_savings=data.get("total_estimated_savings") or 0.0,
            total_realized_savings=data.get("total_realized_savings") or 0.0,
            executed_at=data.get("executed_at"),
            completed_at=data.get("completed_at"),
            execution_duration_seconds=data.get("execution_duration_seconds"),
            expires_at=data.get("expires_at"),
            archived_at=data.get("archived_at"),
            tags=json.loads(data["tags"]) if data.get("tags") else None,
            metadata=json.loads(data["metadata"]) if data.get("metadata") else None,
        )

    def _row_to_action(self, row: tuple) -> PlanAction:
        """Convert database row to PlanAction."""
        columns = [desc[0] for desc in self.conn.description]
        data = dict(zip(columns, row))

        return PlanAction(
            action_id=data["action_id"],
            plan_id=data["plan_id"],
            resource_id=data["resource_id"],
            resource_name=data["resource_name"],
            resource_type=data.get("resource_type", "vm"),
            resource_group=data.get("resource_group"),
            location=data.get("location"),
            subscription_id=data.get("subscription_id"),
            analysis_id=data.get("analysis_id"),
            analysis_type=data["analysis_type"],
            severity=data.get("severity"),  # Already a string from database
            action_type=ActionType(data["action_type"]),
            action_params=json.loads(data["action_params"])
            if data.get("action_params")
            else None,
            estimated_monthly_savings=data.get("estimated_monthly_savings", 0.0),
            realized_monthly_savings=data.get("realized_monthly_savings"),
            status=ActionStatus(data.get("status", "pending")),
            validation_status=data.get("validation_status"),
            validation_details=json.loads(data["validation_details"])
            if data.get("validation_details")
            else None,
            validated_at=data.get("validated_at"),
            execution_started_at=data.get("execution_started_at"),
            execution_completed_at=data.get("execution_completed_at"),
            execution_duration_seconds=data.get("execution_duration_seconds"),
            execution_result=data.get("execution_result"),
            execution_details=json.loads(data["execution_details"])
            if data.get("execution_details")
            else None,
            error_message=data.get("error_message"),
            error_code=data.get("error_code"),
            rollback_possible=data.get("rollback_possible", False),
            rollback_data=json.loads(data["rollback_data"])
            if data.get("rollback_data")
            else None,
            rolled_back_at=data.get("rolled_back_at"),
            rollback_result=data.get("rollback_result"),
            execution_order=data.get("execution_order"),
        )

    def _row_to_history(self, row: tuple) -> ActionHistory:
        """Convert database row to ActionHistory."""
        columns = [desc[0] for desc in self.conn.description]
        data = dict(zip(columns, row))

        return ActionHistory(
            history_id=data["history_id"],
            action_id=data["action_id"],
            plan_id=data["plan_id"],
            timestamp=data["timestamp"],
            event_type=EventType(data["event_type"]),
            previous_status=data.get("previous_status"),
            new_status=data.get("new_status"),
            details=json.loads(data["details"]) if data.get("details") else None,
            performed_by=data.get("performed_by", "system"),
            metadata=json.loads(data["metadata"]) if data.get("metadata") else None,
        )
