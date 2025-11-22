"""Azure VM SKU equivalence mapper for legacy VM resolution.

This module implements the strategy defined in docs/azure_vm_selection_strategy.md
to map legacy Azure VM SKUs to modern equivalents when pricing data is unavailable.

Key functions:
- resolve_equivalent_sku(): Main entry point for SKU resolution
- get_equivalent_from_db(): Database lookup for known mappings
- resolve_by_rules(): Fallback rule-based resolution

The module ensures stable cost analysis even when legacy SKUs are retired
from the Azure Retail Prices API.
"""
from typing import Optional, Dict, Any
import logging
import re

# Internal
from dfo.db.duck import DuckDBManager

logger = logging.getLogger(__name__)


def resolve_equivalent_sku(sku: str) -> Optional[str]:
    """Resolve modern equivalent for a legacy VM SKU.

    This is the main entry point for SKU resolution. It uses a two-tier approach:
    1. Database lookup for known mappings
    2. Rule-based resolution for pattern matching

    Args:
        sku: Azure VM SKU (e.g., "Standard_B1s", "Standard_D2_v2")

    Returns:
        Modern equivalent SKU, or None if no mapping found

    Example:
        >>> resolve_equivalent_sku("Standard_B1s")
        "Standard_B2ls_v2"

        >>> resolve_equivalent_sku("Standard_D2_v2")
        "Standard_D2s_v5"
    """
    if not sku:
        return None

    # Normalize SKU name
    sku = sku.strip()

    # Try database lookup first
    equivalent = get_equivalent_from_db(sku)
    if equivalent:
        logger.info(f"Resolved {sku} → {equivalent} (from database)")
        return equivalent

    # Fallback to rule-based resolution
    equivalent = resolve_by_rules(sku)
    if equivalent:
        logger.info(f"Resolved {sku} → {equivalent} (by rules)")
        return equivalent

    logger.warning(f"No equivalent found for {sku}")
    return None


def get_equivalent_from_db(sku: str) -> Optional[str]:
    """Look up equivalent SKU from vm_equivalence table.

    Args:
        sku: Legacy VM SKU

    Returns:
        Modern equivalent SKU from database, or None if not found
    """
    db = DuckDBManager()

    try:
        rows = db.query(
            """
            SELECT modern_sku, notes
            FROM vm_equivalence
            WHERE legacy_sku = ?
            """,
            (sku,)
        )

        if rows:
            modern_sku = rows[0][0]
            notes = rows[0][1]
            logger.debug(f"Database mapping: {sku} → {modern_sku} ({notes})")
            return modern_sku

        return None

    except Exception as e:
        logger.error(f"Failed to query vm_equivalence table: {e}")
        return None


def resolve_by_rules(sku: str) -> Optional[str]:
    """Rule-based SKU resolution using Azure VM naming patterns.

    Implements the selection rules from docs/azure_vm_selection_strategy.md:
    1. Extract series family (B, D, E, F, etc.)
    2. Extract size and generation
    3. Map to newest generation in same family

    Args:
        sku: VM SKU to resolve

    Returns:
        Modern equivalent SKU based on rules, or None

    Rules:
    - B-series (no v2) → B-series v2
    - A-series → D-series v5
    - D/E/F v1/v2/v3 → same series v5
    """
    # Parse SKU using regex
    # Pattern: Standard_{Series}{Size}[s][_v{Gen}]
    # Examples: Standard_B1s, Standard_D2s_v3, Standard_E4_v2
    pattern = r"Standard_([A-Z]+)(\d+)([a-z]*?)(?:_v(\d+))?$"
    match = re.match(pattern, sku)

    if not match:
        logger.debug(f"SKU {sku} does not match expected pattern")
        return None

    series = match.group(1)  # B, D, E, F, etc.
    size = match.group(2)    # 1, 2, 4, 8, etc.
    modifiers = match.group(3) or ""  # s, ms, ls, etc.
    generation = match.group(4)  # v2, v3, v4, etc.

    logger.debug(
        f"Parsed {sku}: series={series}, size={size}, "
        f"modifiers={modifiers}, gen={generation}"
    )

    # Rule 1: B-series without v2 → B-series v2
    if series == "B" and generation != "2":
        # B1s is smallest, but B-series v2 starts at B2ls_v2
        if size == "1":
            return "Standard_B2ls_v2"
        else:
            # Try to match modifier pattern
            return f"Standard_B{size}{modifiers}_v2"

    # Rule 2: A-series → D-series v5 (general purpose replacement)
    if series == "A":
        # Map to equivalent D-series size
        size_map = {"1": "2", "2": "2", "3": "4", "4": "8", "8": "8"}
        new_size = size_map.get(size, size)
        return f"Standard_D{new_size}s_v5"

    # Rule 3: D/E/F series v1/v2/v3/v4 → v5
    if series in ["D", "E", "F"]:
        if generation in ["1", "2", "3", "4", None]:
            # Ensure 's' modifier for v5 (SSD storage)
            if "s" not in modifiers:
                modifiers = modifiers + "s"
            return f"Standard_{series}{size}{modifiers}_v5"

    # No rule matched
    return None


def get_sku_metadata(sku: str) -> Dict[str, Any]:
    """Get metadata for a VM SKU (legacy or modern).

    Args:
        sku: VM SKU

    Returns:
        Dict with metadata:
            - sku: The SKU name
            - vcpu: vCPU count (if in equivalence table)
            - memory_gb: Memory in GB (if in equivalence table)
            - series_family: Series family (B, D, E, etc.)
            - is_legacy: Whether this is a legacy SKU
            - modern_equivalent: Modern SKU if legacy
    """
    db = DuckDBManager()

    # Check if this is a known legacy SKU
    try:
        rows = db.query(
            """
            SELECT modern_sku, vcpu_legacy, memory_gb_legacy, series_family
            FROM vm_equivalence
            WHERE legacy_sku = ?
            """,
            (sku,)
        )

        if rows:
            return {
                "sku": sku,
                "vcpu": rows[0][1],
                "memory_gb": rows[0][2],
                "series_family": rows[0][3],
                "is_legacy": True,
                "modern_equivalent": rows[0][0]
            }

    except Exception as e:
        logger.debug(f"Could not retrieve metadata for {sku}: {e}")

    # Not a legacy SKU or not in database
    return {
        "sku": sku,
        "is_legacy": False,
        "modern_equivalent": None
    }
