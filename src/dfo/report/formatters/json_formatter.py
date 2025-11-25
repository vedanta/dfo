"""JSON export formatter for reports.

Converts report data models to JSON format with proper datetime serialization.
"""
import json
from typing import Union, Any
from datetime import datetime

from dfo.report.models import RuleViewData, SummaryViewData


def format_to_json(
    data: Union[RuleViewData, SummaryViewData],
    pretty: bool = True
) -> str:
    """Format any view data to JSON.

    Args:
        data: Report data model (RuleViewData or SummaryViewData)
        pretty: If True, format with indentation for readability

    Returns:
        JSON string
    """
    # Convert Pydantic model to dict
    data_dict = data.model_dump()

    # Convert datetime objects to ISO strings
    data_dict = _convert_datetimes(data_dict)

    # Format JSON
    indent = 2 if pretty else None
    return json.dumps(data_dict, indent=indent, ensure_ascii=False)


def _convert_datetimes(obj: Any) -> Any:
    """Recursively convert datetime objects to ISO format strings.

    Args:
        obj: Object that may contain datetime instances

    Returns:
        Object with datetimes converted to strings
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: _convert_datetimes(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetimes(item) for item in obj]
    else:
        return obj
