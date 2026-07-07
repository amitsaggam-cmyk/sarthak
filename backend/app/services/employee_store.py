import json
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import WorkdayEmployeeDetails


def _employee_data_path() -> Path:
    """Resolve the temporary employee JSON file path."""

    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / get_settings().employee_data_path


def load_employees() -> list[WorkdayEmployeeDetails]:
    """Load demo Workday-like employee records from JSON."""

    with _employee_data_path().open("r", encoding="utf-8") as file:
        raw_records = json.load(file)
    return [WorkdayEmployeeDetails(**record) for record in raw_records]


def find_employee(employee_id: str | None, employee_name: str | None) -> WorkdayEmployeeDetails | None:
    """Find a demo employee by exact employee id first, then by case-insensitive name."""

    employees = load_employees()
    if employee_id:
        for employee in employees:
            if employee.employee_id.lower() == employee_id.lower():
                return employee

    if employee_name:
        for employee in employees:
            if employee.employee_name.lower() == employee_name.lower():
                return employee

    return None
