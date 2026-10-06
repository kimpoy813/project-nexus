"""Shared parsing for the standalone and nested Extension Target editors."""

TARGET_NUMBER_FIELDS = (
    ("planned_q1", "Planned Q1"),
    ("planned_q2", "Planned Q2"),
    ("planned_q3", "Planned Q3"),
    ("planned_q4", "Planned Q4"),
    ("actual_q1", "Actual Q1"),
    ("actual_q2", "Actual Q2"),
    ("actual_q3", "Actual Q3"),
    ("actual_q4", "Actual Q4"),
)


def _parse_target_numbers(data):
    """Return non-negative integer target values from request-like data.

    Every figure is planned or accomplished by quarter, so blanks are
    intentionally treated as zero: an administrator can fill the quarters in
    as the year progresses.  The yearly totals are derived, never posted.
    """

    values = {}
    for field, label in TARGET_NUMBER_FIELDS:
        raw_value = data.get(field)
        if raw_value in (None, ""):
            raw_value = 0
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a whole number.") from exc
        if value < 0:
            raise ValueError(f"{label} cannot be negative.")
        values[field] = value
    return values
