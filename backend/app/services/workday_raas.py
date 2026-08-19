from datetime import date, datetime
import logging
from typing import Any


import httpx


from app.core.config import Settings, get_settings
from app.models.schemas import ClaimedEmployeeDetails, WorkdayEmployeeDetails




logger = logging.getLogger(__name__)




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
   
    logger.debug("Extracting rows from payload. Payload type: %s", type(payload).__name__)


    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
        logger.info("Payload is a list. Extracted %d dictionary rows.", len(rows))
        return rows
       
    if isinstance(payload, dict):
        for key in ("Report_Entry", "report_entry", "rows", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = [row for row in value if isinstance(row, dict)]
                logger.info("Found key '%s' in payload dict. Extracted %d dictionary rows.", key, len(rows))
                return rows
               
        logger.warning("Payload is a dict but no known list keys were found. Returning as a single row.")
        return [payload]
       
    logger.warning("Unrecognized payload shape (not a list or dict). Returning empty list.")
    return []




def _get_field(row: dict, configured_field: str, fallback_keys: tuple[str, ...]) -> Any:
    """Look up a value using the configured field name first, then fall back to
    known alternate key spellings Workday RaaS commonly returns (e.g. with a
    'wd:' namespace prefix, or different casing)."""


    if configured_field in row:
        return row.get(configured_field)
    for key in fallback_keys:
        if key in row:
            return row.get(key)
    return None




async def fetch_workday_details(claimed: ClaimedEmployeeDetails) -> WorkdayEmployeeDetails | None:
    """Look up the employee in Workday RaaS using env-driven field mappings."""


    settings = get_settings()
    if not settings.workday_raas_url:
        logger.warning("[WORKDAY] WORKDAY_RAAS_URL is not configured")
        return None


    if not (claimed.employee_id or claimed.candidate_name):
        logger.warning("[WORKDAY] No employee name/id available for lookup")
        return None


    logger.debug(
        "[WORKDAY] Lookup values employee_id=%r candidate_name=%r",
        claimed.employee_id,
        claimed.candidate_name,
    )


    auth = None
    if settings.workday_raas_username or settings.workday_raas_password:
        # Use explicit BasicAuth so credentials are always sent as Basic auth
        auth = httpx.BasicAuth(settings.workday_raas_username or "", settings.workday_raas_password or "")


    async with httpx.AsyncClient(timeout=60.0, verify=settings.workday_raas_verify_ssl) as client:
        logger.info(
            "[WORKDAY] Calling RaaS base url=%s",
            settings.workday_raas_url,
        )
        try:
            response = await client.get(settings.workday_raas_url, params={"format": "json"}, auth=auth)
            # Do NOT raise here; handle non-200 gracefully
            logger.info("[WORKDAY] RaaS response status=%s for url=%s", response.status_code, response.url)
            logger.debug("[WORKDAY] RaaS response headers=%s", response.headers)
            logger.debug("[WORKDAY] RaaS response body=%s", response.text)


            if response.status_code != 200:
                logger.warning("[WORKDAY] RaaS returned status=%s for url=%s", response.status_code, response.url)
                return None


            row = _find_matching_row(response.json(), claimed, settings)
            if not row:
                logger.info("[WORKDAY] No matching row found for employee_id=%r candidate_name=%r", claimed.employee_id, claimed.candidate_name)
                return None
        except httpx.HTTPError as exc:
            logger.warning("[WORKDAY] RaaS request failed: %s", exc)
            return None


    if not row:
        return None


    return WorkdayEmployeeDetails(
        employee_id=_get_field(row, settings.workday_employee_id_field, ("wd:Employee_ID", "Employee_ID", "employee_id")),
        employee_name=_get_field(row, settings.workday_employee_name_field, ("wd:Name", "Name", "candidate_name")),
        nature_of_employment=_get_field(row, settings.workday_nature_of_employment_field, ("wd:Nature_of_Employment", "Nature_of_Employment", "wd:Nature_Of_Employment", "Nature_Of_Employment")),
        start_date=_parse_date(_get_field(row, settings.workday_start_date_field, ("wd:Date_Of_Joining", "Date_Of_Joining", "wd:Start_Date", "Start_Date"))),
        end_date=_parse_date(_get_field(row, settings.workday_end_date_field, ("wd:Date_Of_Leaving", "Date_Of_Leaving", "wd:End_Date", "End_Date"))),
        last_designation=_get_field(row, settings.workday_last_designation_field, ("wd:Last_Designation", "Last_Designation")),
        location=_get_field(row, settings.workday_location_field, ("wd:Location", "Location")),
        exit_formalities_completed=_get_field(row, settings.workday_exit_formalities_completed_field, ("wd:Exit_Formalities_Completed", "Exit_Formalities_Completed")),
    )




def _find_matching_row(payload: Any, claimed: ClaimedEmployeeDetails, settings: "Settings") -> dict | None:
    """Extract rows and find the first row matching claimed employee_id or candidate_name."""


    rows = _rows_from_payload(payload)
    if not rows:
        logger.warning("No rows extracted from payload for Workday matching.")
        return None


    logger.debug("[WORKDAY] Matching against %d rows", len(rows))
    logger.debug("[WORKDAY] Sample row keys: %s", list(rows[0].keys()))


    def normalize(value: Any) -> str:
        return str(value).strip().lower() if value is not None else ""


    claimed_employee_id = normalize(claimed.employee_id)
    claimed_candidate_name = normalize(claimed.candidate_name)


    # Common alternate spellings seen across different Workday RaaS reports.
    employee_id_fallbacks = ("wd:Employee_ID", "Employee_ID", "employee_id")
    candidate_name_fallbacks = ("wd:Name", "Name", "candidate_name")


    if claimed_employee_id:
        for row in rows:
            value = normalize(_get_field(row, settings.workday_employee_id_field, employee_id_fallbacks))
            if value and value == claimed_employee_id:
                logger.info("Matched row by employee_id (configured field='%s').", settings.workday_employee_id_field)
                return row


    if claimed_candidate_name:
        for row in rows:
            value = normalize(_get_field(row, settings.workday_employee_name_field, candidate_name_fallbacks))
            if value and value == claimed_candidate_name:
                logger.info("Matched row by candidate_name (configured field='%s').", settings.workday_employee_name_field)
                return row


    logger.info("No Workday row matched employee_id=%r or candidate_name=%r.", claimed.employee_id, claimed.candidate_name)
    return None



