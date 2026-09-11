"""Convert editable panel text to API JSON values before transmission."""

import math


def integer_input(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not an integer input")
    text = str(value).strip()
    return int(text, 16 if text.lower().lstrip("+-").startswith("0x") else 10)


def parameter_input(value, data_type):
    kind = str(data_type).lower()
    if kind.startswith(("uint", "int")) or kind == "udint":
        return integer_input(value)
    if kind.startswith("float"):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("A finite numeric value is required")
        return result
    if kind == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"true", "1"}:
            return True
        if text in {"false", "0"}:
            return False
        raise ValueError("A Boolean value is required")
    return value
