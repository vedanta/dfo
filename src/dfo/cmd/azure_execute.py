"""Azure direct execution commands.

This module provides CLI commands for direct execution of optimization actions
on individual Azure resources. Direct execution bypasses the plan-based workflow
and executes actions immediately (with safety confirmations).

Commands:
    ./dfo azure execute vm <vm-name> <action> [options]

Safety:
    - Feature flag required (DFO_ENABLE_DIRECT_EXECUTION=true)
    - Dry-run by default (use --no-dry-run for live execution)
    - Confirmation prompts (use --yes to skip)
    - Resource and action validation
    - Comprehensive logging
"""
from typing import Optional

import typer
from rich.console import Console

from dfo.execute.direct import (
    DirectExecutionManager,
    DirectExecutionRequest,
    FeatureDisabledError,
    ResourceNotFoundError,
    ValidationError,
    ExecutionError,
)

app = typer.Typer(help="Direct execution commands")
console = Console()


@app.command("vm")
def execute_vm(
    vm_name: str = typer.Argument(..., help="VM name"),
    action: str = typer.Argument(
        ...,
        help="Action to perform: stop, deallocate, delete, downsize, restart"
    ),
    resource_group: str = typer.Option(
        ...,
        "--resource-group", "-g",
        help="Resource group name"
    ),
    target_sku: Optional[str] = typer.Option(
        None,
        "--target-sku", "-t",
        help="Target SKU for downsize action (required for downsize)"
    ),
    reason: Optional[str] = typer.Option(
        None,
        "--reason", "-r",
        help="Reason for the action (for audit trail)"
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry-run mode (default: true). Use --no-dry-run for live execution."
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompts"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force execution, skip all safety checks (DANGEROUS!)"
    ),
    no_validation: bool = typer.Option(
        False,
        "--no-validation",
        help="Skip validation checks (VERY DANGEROUS!)"
    ),
):
    """Execute action on a single VM.

    This command allows direct execution of optimization actions on individual VMs
    without the plan-based workflow. Use with caution in production environments.

    Examples:
        # Dry-run stop (safe, shows what would happen)
        ./dfo azure execute vm my-vm stop -g my-rg

        # Live stop with confirmation
        ./dfo azure execute vm my-vm stop -g my-rg --no-dry-run

        # Live stop with auto-confirm
        ./dfo azure execute vm my-vm stop -g my-rg --no-dry-run --yes

        # Deallocate with reason
        ./dfo azure execute vm my-vm deallocate -g my-rg --reason "Cost savings"

        # Downsize (requires target SKU)
        ./dfo azure execute vm my-vm downsize -g my-rg -t Standard_B2s

        # Delete (very dangerous!)
        ./dfo azure execute vm my-vm delete -g my-rg --no-dry-run

    Safety Features:
        - Feature flag required (DFO_ENABLE_DIRECT_EXECUTION=true)
        - Dry-run by default (prevents accidental live execution)
        - Confirmation prompts for live execution
        - Resource validation (checks VM exists)
        - Action validation (checks action is valid for current state)
        - Azure validation (checks for protection tags)
        - Comprehensive logging (all actions logged to database)

    Flags:
        --dry-run: Simulate execution without making changes (default)
        --no-dry-run: Execute for real (requires confirmation)
        --yes: Skip confirmation prompts
        --force: Skip safety checks (use only in emergencies!)
        --no-validation: Skip all validation (VERY DANGEROUS!)

    Requirements:
        - DFO_ENABLE_DIRECT_EXECUTION=true in .env
        - Azure credentials configured
        - Appropriate RBAC permissions
    """
    try:
        # Create execution request
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name=vm_name,
            action=action,
            resource_group=resource_group,
            target_sku=target_sku,
            reason=reason,
            dry_run=dry_run,
            yes=yes,
            force=force,
            no_validation=no_validation
        )

        # Execute
        manager = DirectExecutionManager()
        result = manager.execute(request)

        # Exit with appropriate code
        if result.success:
            raise typer.Exit(0)
        else:
            raise typer.Exit(1)

    except FeatureDisabledError as e:
        console.print(f"[red]✗ Feature Disabled[/red]")
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1)

    except ResourceNotFoundError as e:
        console.print(f"[red]✗ Resource Not Found[/red]")
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1)

    except ValidationError as e:
        console.print(f"[red]✗ Validation Failed[/red]")
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1)

    except ExecutionError as e:
        console.print(f"[red]✗ Execution Failed[/red]")
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]✗ Unexpected Error[/red]")
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
