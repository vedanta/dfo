"""Terminal capability detection utilities.

This module provides utilities for detecting terminal capabilities
and determining the appropriate display mode for CLI output.

Per CODE_STYLE.md:
- This is a common utility module
- No business logic or external dependencies
- Pure functions for terminal detection
"""
import shutil
import sys
from typing import Literal

DisplayMode = Literal["simple", "rich"]


def get_display_mode(min_width: int = 100) -> DisplayMode:
    """Detect terminal capabilities and return appropriate display mode.

    Determines whether to use simple (compact) or rich (detailed) progress display
    based on terminal width and TTY status.

    Args:
        min_width: Minimum terminal width for rich mode (default: 100 columns)

    Returns:
        "simple" for narrow terminals or non-TTY (compact progress)
        "rich" for wide terminals with TTY (detailed progress tree)

    Examples:
        >>> get_display_mode()  # Wide terminal
        'rich'
        >>> get_display_mode(min_width=200)  # Terminal too narrow
        'simple'

    Design:
        - Narrow terminals (< min_width): simple mode
        - Non-interactive (piped, CI): simple mode
        - Wide interactive terminals: rich mode
        - Graceful fallback: simple mode on any error
    """
    try:
        # Get terminal size
        terminal_size = shutil.get_terminal_size()

        # Check width threshold
        if terminal_size.columns < min_width:
            return "simple"

        # Check if running in CI/non-interactive environment
        if not sys.stdout.isatty():
            return "simple"

        # Wide terminal with TTY support - use rich mode
        return "rich"

    except Exception:
        # Fallback to simple mode on any error (defensive programming)
        return "simple"
