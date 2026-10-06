"""Shared parsing for the standalone and nested Extension Target editors."""

TARGET_NUMBER_FIELDS = (
    ("target", "Annual target"),
    ("actual_q1", "Actual Q1"),
    ("actual_q2", "Actual Q2"),
    ("actual_q3", "Actual Q3"),
    ("actual_q4", "Actual Q4"),
)


def _parse_target_numbers(data):
    """Return non-negative integer target values from request-like data.

    The annual target is required. Blank quarterly actuals are intentionally
    treated as zero so an administrator can fill them as the year progresses.
    """

    values = {}
    for field, label in TARGET_NUMBER_FIELDS:
        raw_value = data.get(field)
        if field != "target" and raw_value in (None, ""):
            raw_value = 0
        if field == "target" and raw_value in (None, ""):
            raise ValueError("Annual target is required.")
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a whole number.") from exc
        if value < 0:
            raise ValueError(f"{label} cannot be negative.")
        values[field] = value
    return values
