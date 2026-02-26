"""Utilities for safe data parsing."""

def safe_float(value, default=0.0) -> float:
    """Safely convert any value to float, handling None and strings."""
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.replace(',', '.').replace('г', '').strip()
        return float(value)
    except (ValueError, TypeError):
        return default
