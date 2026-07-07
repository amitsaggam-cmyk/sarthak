import re
from datetime import date, datetime

from app.models.schemas import ClaimedEmployeeDetails


DATE_PATTERNS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
)


def _extract_line_value(body: str, labels: list[str]) -> str | None:
    """Find a value written after any accepted label in the email body."""

    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*[:\-]\s*(.+)", body, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _parse_date(value: str | None) -> date | None:
    """Parse common HR email date formats into a real date object."""

    if not value:
        return None

    clean_value = value.strip().rstrip(".")
    for pattern in DATE_PATTERNS:
        try:
            return date.fromisoformat(clean_value) if pattern == "%Y-%m-%d" else datetime.strptime(
                clean_value, pattern
            ).date()
        except ValueError:
            continue
    return None


def parse_verification_email(body: str) -> ClaimedEmployeeDetails:
    """Convert the requesting company's email text into structured claim data."""

    employee_id = _extract_line_value(body, ["Employee ID", "Emp ID", "Employee Code"])
    employee_name = _extract_line_value(body, ["Employee Name", "Name"])
    joining_date = _extract_line_value(body, ["Date of Joining", "DOJ", "Joining Date"])
    last_day = _extract_line_value(body, ["Last Working Day", "LWD", "Relieving Date"])

    return ClaimedEmployeeDetails(
        employee_id=employee_id,
        employee_name=employee_name,
        date_of_joining=_parse_date(joining_date),
        last_working_day=_parse_date(last_day),
    )
