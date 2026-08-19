import re
import logging
from datetime import date, datetime

from app.models.schemas import ClaimedEmployeeDetails

logger = logging.getLogger(__name__)
DATE_PATTERNS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
)


def _extract_line_value(body: str, labels: list[str]) -> str | None:
    lines = body.splitlines()
    for line in lines:
        line = line.strip()
        for label in labels:
            # Handles list formats with optional spaces and leading bullets like "-", "*", or "•"
            pattern = rf"^\s*[\-\*\u2022]?\s*{re.escape(label)}\s*:\s*(.+)$"
            match = re.match(pattern, line, re.IGNORECASE)

            if match:
                return match.group(1).strip()

    return None


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
    logger.debug("[PROCESS] Parsing verification email body_chars=%s", len(body))
    print("========== EMAIL BODY ==========")
    print(repr(body))
    print("================================")
    
    
    body = re.sub(r"[*_`]", "", body)
    
    candidate_name = _extract_line_value(body, ["Candidate Name", "Employee Name", "Name"])
    employee_id = _extract_line_value(body, ["Employee ID", "Emp ID", "ID"])
    nature_of_employment = _extract_line_value(body, ["Nature of Employment", "Employment Type", "Type"])
    start_date = _extract_line_value(body, ["Start Date", "Date of Joining", "DOJ", "Joining Date"])
    end_date = _extract_line_value(body, ["End Date", "Last Working Day", "LWD", "Relieving Date"])
    last_designation = _extract_line_value(body, ["Last Designation", "Designation", "Title", "Position"])
    location = _extract_line_value(body, ["Location", "Base Location", "Work Location"])
    exit_formalities_completed = _extract_line_value(body, ["Exit Formalities", "Exit Formalities Completed", "Clearance"])

    logger.debug(
        "[PROCESS] Parsed fallback fields candidate_name=%r employee_id=%r start_date=%r end_date=%r",
        candidate_name,
        employee_id,
        start_date,
        end_date,
    )

    return ClaimedEmployeeDetails(
        candidate_name=candidate_name,
        employee_id=employee_id,
        nature_of_employment=nature_of_employment,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        last_designation=last_designation,
        location=location,
        exit_formalities_completed=exit_formalities_completed,
    )