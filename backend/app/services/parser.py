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
    lines = body.splitlines()
    for line in lines:
        line = line.strip()
        for label in labels:
            pattern = rf"^{re.escape(label)}\s*:\s*(.+)$"
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
    print("========== EMAIL BODY ==========")
    print(repr(body))
    print("================================")
   
    body = re.sub(r"[*_`]", "", body)
    employee_name = _extract_line_value(body, ["Employee Name", "Name"])
    joining_date = _extract_line_value(body, ["Date of Joining", "DOJ", "Joining Date"])
    last_day = _extract_line_value(body, ["Last Working Day", "LWD", "Relieving Date"])


    print("Employee:", repr(employee_name))
    print("Joining:", repr(joining_date))
    print("Last Day:", repr(last_day))


    return ClaimedEmployeeDetails(
        employee_name=employee_name,
        date_of_joining=_parse_date(joining_date),
        last_working_day=_parse_date(last_day),
    )





