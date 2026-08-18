from collections.abc import Iterator
from typing import Any


def diff_payloads(previous: dict[str, Any], current: dict[str, Any], path: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield deterministic structural JSON differences without LLM interpretation."""
    for key in sorted(set(previous) | set(current)):
        field_path = f"{path}.{key}"
        if key not in previous:
            yield "field_added", {"path": field_path, "old_value": None, "new_value": current[key]}
        elif key not in current:
            yield "field_removed", {"path": field_path, "old_value": previous[key], "new_value": None}
        elif isinstance(previous[key], dict) and isinstance(current[key], dict):
            yield from diff_payloads(previous[key], current[key], field_path)
        elif previous[key] != current[key]:
            yield "value_changed", {"path": field_path, "old_value": previous[key], "new_value": current[key]}
