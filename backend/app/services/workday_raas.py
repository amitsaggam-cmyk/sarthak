from datetime import date, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.schemas import ClaimedEmployeeDetails, WorkdayEmployeeDetails


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text, fmt).date()
        except ValueError:
            continue
    return None


def _rows_from_payload(payload: Any) -> list[dict]:
    """Handle common Workday RaaS JSON shapes without locking to one report."""

    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("Report_Entry", "report_entry", "rows", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        return [payload]
    return []


async def fetch_workday_details(claimed: ClaimedEmployeeDetails) -> WorkdayEmployeeDetails | None:
    """Look up the employee in Workday RaaS using env-driven field mappings."""

    settings = get_settings()
    if not settings.workday_raas_url:
        return None

    lookup_value = claimed.employee_name or claimed.employee_id
    if not lookup_value:
        return None

    params = {
        settings.workday_lookup_param: lookup_value,
        "format": "json",
    }
    auth = None
    if settings.workday_raas_username or settings.workday_raas_password:
        auth = (settings.workday_raas_username, settings.workday_raas_password)

    async with httpx.AsyncClient(timeout=60.0, verify=settings.workday_raas_verify_ssl) as client:
        response = await client.get(settings.workday_raas_url, params=params, auth=auth)
        response.raise_for_status()
        rows = _rows_from_payload(response.json())

    if not rows:
        return None

    row = rows[0]
    return WorkdayEmployeeDetails(
        employee_id=row.get(settings.workday_employee_id_field),
        employee_name=row.get(settings.workday_employee_name_field),
        date_of_joining=_parse_date(row.get(settings.workday_date_of_joining_field)),
        last_working_day=_parse_date(row.get(settings.workday_last_working_day_field)),
    )
