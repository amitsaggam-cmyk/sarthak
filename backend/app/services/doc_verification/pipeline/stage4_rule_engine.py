import re
from datetime import datetime
from typing import Any


MANDATORY_DOC_TYPES = {
    "PAN_CARD",
    "AADHAAR_CARD",
    "RESUME",
    "SELF_DECLARATION_FORM",
    "PF_FORM_11",
    "CANCELLED_CHEQUE",
    "SIGNED_OFFER_LETTER_JADE",
    "PASSPORT_PHOTO",
}


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^a-z0-9\s]", "", str(text).lower())
    return " ".join(sorted(word for word in cleaned.split() if word))


def _normalize_exact(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", "", str(value)).upper()


def _parse_iso_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _calculate_days_between(date_str_1: str | None, date_str_2: str | None) -> int:
    first = _parse_iso_date(date_str_1)
    second = _parse_iso_date(date_str_2)
    if not first or not second:
        return -9999
    return abs((first - second).days)


def _get_all_instances(dossier: dict[str, Any], doc_type: str) -> list[dict[str, Any]]:
    doc = dossier.get(doc_type)
    if doc is None:
        return []
    entries = doc if isinstance(doc, list) else [doc]
    return [entry.get("extracted_data", {}) for entry in entries if isinstance(entry, dict)]


def _get_all_documents(dossier: dict[str, Any], doc_type: str) -> list[dict[str, Any]]:
    doc = dossier.get(doc_type)
    if doc is None:
        return []
    entries = doc if isinstance(doc, list) else [doc]
    return [entry for entry in entries if isinstance(entry, dict)]


def _unwrap_doc(dossier: dict[str, Any], doc_type: str) -> dict[str, Any]:
    instances = _get_all_instances(dossier, doc_type)
    return instances[0] if instances else {}


FIELD_SOURCES: dict[str, list[tuple[str, str]]] = {
    "name": [
        ("PAN_CARD", "name"),
        ("AADHAAR_CARD", "name"),
        ("SELF_DECLARATION_FORM", "candidate_name"),
        ("PF_FORM_11", "candidate_name"),
        ("RESUME", "candidate_name"),
        ("OFFER_LETTER_PREVIOUS_ORG", "candidate_name"),
        ("SIGNED_OFFER_LETTER_JADE", "candidate_name"),
    ],
    "dob": [("PAN_CARD", "dob"), ("AADHAAR_CARD", "dob")],
    "doj": [("SELF_DECLARATION_FORM", "doj")],
    "account_number": [("PF_FORM_11", "account_number"), ("CANCELLED_CHEQUE", "account_number")],
    "ifsc_code": [("PF_FORM_11", "ifsc_code"), ("CANCELLED_CHEQUE", "ifsc_code")],
    "pan_number": [("PAN_CARD", "pan_number"), ("PF_FORM_11", "pan_number")],
    "aadhaar_number": [("AADHAAR_CARD", "aadhaar_number"), ("PF_FORM_11", "aadhaar_number")],
}

FIELD_NORMALIZERS = {
    "name": _normalize_text,
    "dob": _normalize_exact,
    "doj": _normalize_exact,
    "account_number": _normalize_exact,
    "ifsc_code": _normalize_exact,
    "pan_number": _normalize_exact,
    "aadhaar_number": _normalize_exact,
}

COMPANY_MENTION_SOURCES = [
    ("OFFER_LETTER_PREVIOUS_ORG", "company_name"),
    ("PAYSLIP", "company_name"),
    ("RESIGNATION_ACCEPTANCE", "company_name"),
    ("RELIEVING_LETTER", "company_name"),
]


def _collect_field_values(
    dossier: dict[str, Any],
    sources: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    collected = []
    for doc_type, field_name in sources:
        for index, data in enumerate(_get_all_instances(dossier, doc_type)):
            value = data.get(field_name)
            if not value:
                continue
            label = doc_type if index == 0 else f"{doc_type}#{index + 1}"
            collected.append((label, str(value)))
    return collected


def _check_field_consistency(dossier: dict[str, Any], field_key: str, issues: list[str]) -> None:
    sources = FIELD_SOURCES.get(field_key, [])
    normalize_fn = FIELD_NORMALIZERS.get(field_key, _normalize_text)
    collected = _collect_field_values(dossier, sources)
    if len(collected) < 2:
        return

    seen_pairs = set()
    field_display = field_key.replace("_", " ").upper()
    for i, (pivot_label, pivot_raw) in enumerate(collected):
        mismatches = []
        for j, (target_label, target_raw) in enumerate(collected):
            if i == j:
                continue
            pair_key = tuple(sorted([pivot_label, target_label]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            if normalize_fn(pivot_raw) != normalize_fn(target_raw):
                mismatches.append(f"{target_label} ('{target_raw}')")
        if mismatches:
            issues.append(
                f"{field_display} Mismatch: {pivot_label} ('{pivot_raw}') does not match: "
                f"{', '.join(mismatches)}."
            )


def _mark_name_status(document: dict[str, Any], field_name: str, status: str, message: str) -> None:
    field_statuses = document.setdefault("field_statuses", {})
    field_statuses[field_name] = {
        "status": status,
        "label": "Match" if status == "match" else "Mismatch",
        "message": message,
    }


def _candidate_name_field(extracted: dict[str, Any]) -> str | None:
    for field_name in ("name", "candidate_name"):
        value = extracted.get(field_name)
        if value and str(value).strip():
            return field_name
    return None


def _check_name_consistency(dossier: dict[str, Any], issues: list[str]) -> None:
    pan_docs = _get_all_documents(dossier, "PAN_CARD")
    aadhaar_docs = _get_all_documents(dossier, "AADHAAR_CARD")
    pan_doc = pan_docs[0] if pan_docs else None
    aadhaar_doc = aadhaar_docs[0] if aadhaar_docs else None
    pan_name = (pan_doc or {}).get("extracted_data", {}).get("name")
    aadhaar_name = (aadhaar_doc or {}).get("extracted_data", {}).get("name")
    normalized_pan = _normalize_text(str(pan_name)) if pan_name else ""
    normalized_aadhaar = _normalize_text(str(aadhaar_name)) if aadhaar_name else ""

    source_names_match = bool(normalized_pan and normalized_aadhaar and normalized_pan == normalized_aadhaar)
    canonical_name = str(aadhaar_name or pan_name or "").strip()
    canonical_normalized = normalized_aadhaar or normalized_pan

    if not source_names_match:
        if normalized_pan and normalized_aadhaar:
            issues.append(
                f"NAME Mismatch: PAN_CARD ('{pan_name}') does not match AADHAAR_CARD ('{aadhaar_name}')."
            )
        else:
            issues.append("NAME Mismatch: Candidate name could not be verified from both PAN Card and Aadhaar Card.")

    for doc_type, document_or_documents in dossier.items():
        documents = document_or_documents if isinstance(document_or_documents, list) else [document_or_documents]
        for index, document in enumerate(documents):
            if not isinstance(document, dict):
                continue
            extracted = document.get("extracted_data") or {}
            if not isinstance(extracted, dict):
                continue
            field_name = _candidate_name_field(extracted)
            if not field_name:
                continue

            label = doc_type if index == 0 else f"{doc_type}#{index + 1}"
            raw_name = str(extracted.get(field_name) or "").strip()

            if not source_names_match:
                _mark_name_status(
                    document,
                    field_name,
                    "mismatch",
                    "PAN Card and Aadhaar Card names do not match, so candidate name cannot be trusted.",
                )
                continue

            if _normalize_text(raw_name) == canonical_normalized:
                _mark_name_status(
                    document,
                    field_name,
                    "match",
                    f"Matches candidate name from PAN Card and Aadhaar Card: {canonical_name}.",
                )
            else:
                _mark_name_status(
                    document,
                    field_name,
                    "mismatch",
                    f"Does not match candidate name from PAN Card and Aadhaar Card: {canonical_name}.",
                )
                issues.append(
                    f"NAME Mismatch: {label} ('{raw_name}') does not match candidate name "
                    f"from PAN_CARD/AADHAAR_CARD ('{canonical_name}')."
                )


def _check_employer_consistency(dossier: dict[str, Any], issues: list[str]) -> None:
    resume_instances = _get_all_instances(dossier, "RESUME")
    resume_employers = [
        _normalize_text(employer)
        for resume in resume_instances
        for employer in (resume.get("employers") or [])
        if employer
    ]
    if not resume_employers:
        return

    for uan_data in _get_all_instances(dossier, "UAN_SCREENSHOT"):
        for entry in uan_data.get("employment_history") or []:
            company = _normalize_text(entry.get("company_name", ""))
            if company and not any(company in employer for employer in resume_employers):
                issues.append(
                    f"Resume Validation: Employer '{entry.get('company_name')}' found in UAN "
                    "but missing from Resume."
                )

    for doc_type, field_name in COMPANY_MENTION_SOURCES:
        for index, data in enumerate(_get_all_instances(dossier, doc_type)):
            company = _normalize_text(data.get(field_name, ""))
            if company and not any(company in employer for employer in resume_employers):
                label = doc_type if index == 0 else f"{doc_type}#{index + 1}"
                issues.append(
                    f"Resume Validation: Employer '{data.get(field_name)}' from {label} "
                    "not found in Resume's employer list."
                )


def evaluate_dossier(
    dossier: dict[str, Any],
    candidate_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_profile = candidate_profile or {}
    issues: list[str] = []
    pending_documents: list[str] = []
    uploaded_types = set(dossier.keys())

    missing_docs = MANDATORY_DOC_TYPES - uploaded_types
    if not ({"MARKSHEET", "DEGREE_CERTIFICATE"} & uploaded_types):
        missing_docs.add("MARKSHEET_OR_DEGREE_CERTIFICATE")
    if missing_docs:
        issues.append(f"Missing mandatory documents: {', '.join(sorted(missing_docs))}")

    _check_name_consistency(dossier, issues)
    for field_key in FIELD_SOURCES:
        if field_key == "name":
            continue
        _check_field_consistency(dossier, field_key, issues)
    _check_employer_consistency(dossier, issues)

    aadhaar = _unwrap_doc(dossier, "AADHAAR_CARD")
    if aadhaar:
        digits_only = re.sub(r"\D", "", str(aadhaar.get("aadhaar_number", "")))
        if digits_only and len(digits_only) != 12:
            issues.append(f"Invalid Aadhaar format: Must be exactly 12 digits, found {len(digits_only)}.")

    pf_form = _unwrap_doc(dossier, "PF_FORM_11")
    if pf_form and pf_form.get("is_signed") is False:
        issues.append("PF Form 11 appears unsigned.")

    self_dec = _unwrap_doc(dossier, "SELF_DECLARATION_FORM")
    if self_dec and self_dec.get("is_signed") is False:
        issues.append("Self Declaration Form appears unsigned.")
    if self_dec and self_dec.get("is_handwritten") is False:
        issues.append("Self Declaration Form must be manually handwritten, not digitally filled.")

    photo = _unwrap_doc(dossier, "PASSPORT_PHOTO")
    if photo:
        if photo.get("has_plain_background") is False:
            issues.append("Passport photo must have a plain white background.")
        if photo.get("is_professional_photo") is False:
            issues.append("Passport photo must be a professional candidate photograph.")

    jade_offer = _unwrap_doc(dossier, "SIGNED_OFFER_LETTER_JADE")
    if jade_offer and (not jade_offer.get("grade") or not jade_offer.get("location")):
        issues.append("Jade Offer Letter missing Grade or Location details.")

    resume = (_get_all_instances(dossier, "RESUME") or [{}])[0]
    resume_employers = resume.get("employers", [])
    has_experience_docs = any(
        _get_all_instances(dossier, doc_type)
        for doc_type in ("UAN_SCREENSHOT", "OFFER_LETTER_PREVIOUS_ORG", "PAYSLIP")
    )
    marksheet = _unwrap_doc(dossier, "MARKSHEET")
    passing_year = marksheet.get("passing_year")
    date_of_joining = _parse_iso_date(self_dec.get("doj"))

    is_fresher = False
    if not resume_employers and not has_experience_docs:
        is_fresher = True
    elif passing_year and date_of_joining and int(passing_year) >= date_of_joining.year:
        is_fresher = True
    elif candidate_profile.get("is_fresher") is True:
        is_fresher = True

    if pf_form:
        if pf_form.get("is_handwritten") is False:
            issues.append("PF Form 11 must be manually handwritten, not digitally filled.")
        if pf_form.get("total_points_filled") is not None:
            required_points = 11
            if pf_form["total_points_filled"] < required_points:
                candidate_type = "Fresher" if is_fresher else "Lateral"
                issues.append(
                    f"PF Form 11 Incomplete: {candidate_type} candidate requires "
                    f"all {required_points} points filled, but found {pf_form['total_points_filled']}."
                )
        else:
            issues.append(
                "PF Form 11 completeness could not be verified because filled point count was not extracted."
            )

    resignation = _unwrap_doc(dossier, "RESIGNATION_ACCEPTANCE")
    relieving = _unwrap_doc(dossier, "RELIEVING_LETTER")
    self_dec_doj = self_dec.get("doj")
    lwd_date = resignation.get("last_working_day") or relieving.get("last_working_day")

    if not is_fresher:
        if "OFFER_LETTER_PREVIOUS_ORG" not in uploaded_types:
            issues.append("Previous Organization Offer Letter is missing.")

        all_payslip_months = {
            str(month).strip()
            for payslip in _get_all_instances(dossier, "PAYSLIP")
            for month in (payslip.get("months_provided") or [])
            if month
        }
        if len(all_payslip_months) < 3:
            issues.append(
                f"Payslip Validation: Expected 3 months leading up to LWD, "
                f"found {len(all_payslip_months)} across all payslip document(s)."
            )

        uan = _unwrap_doc(dossier, "UAN_SCREENSHOT")
        uan_history = uan.get("employment_history") or []
        if uan_history:
            try:
                uan_history_sorted = sorted(
                    uan_history,
                    key=lambda item: datetime.strptime(item["start_date"], "%Y-%m-%d"),
                    reverse=True,
                )
                most_recent_org = uan_history_sorted[0]
                if most_recent_org.get("end_date") and lwd_date and most_recent_org["end_date"] != lwd_date:
                    issues.append(
                        "UAN end date for the most recent organization does not match "
                        "the LWD on resignation/relieving docs."
                    )
                for older_org in uan_history_sorted[1:]:
                    if not older_org.get("end_date"):
                        issues.append(
                            f"UAN Validation: Missing end date for past employer "
                            f"'{older_org.get('company_name')}'."
                        )
            except (TypeError, ValueError, KeyError):
                issues.append("UAN Validation: Invalid date formats found in UAN employment history.")

        if self_dec_doj and lwd_date:
            days_gap = _calculate_days_between(self_dec_doj, lwd_date)
            if days_gap != -9999:
                if days_gap <= 3:
                    if not relieving:
                        pending_documents.append(
                            "Immediate Past Relieving Letter (marked pending due to fast transition)"
                        )
                    if not resignation:
                        issues.append(
                            "Fast transition detected: Immediate relieving letter is waived, "
                            "but Resignation Acceptance is missing."
                        )
                elif not relieving:
                    issues.append(
                        "Standard transition detected: Formal Relieving Letter from most "
                        "recent employer is mandatory."
                    )

    gap_start_date = lwd_date
    if is_fresher and passing_year:
        gap_start_date = f"{passing_year}-07-01"

    if self_dec_doj and gap_start_date:
        days_gap = _calculate_days_between(self_dec_doj, gap_start_date)
        if days_gap != -9999:
            if days_gap > 180 and "GAP_DECLARATION_FORM" not in uploaded_types:
                issues.append(f"Employment/Education gap of {days_gap} days detected. Gap Declaration Form is missing.")
            if days_gap > 365 and "GAP_AFFIDAVIT" not in uploaded_types:
                issues.append(f"Gap of {days_gap} days detected. Notarized Gap Affidavit on stamp paper is missing.")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "pending_documents": pending_documents,
        "dossier_status": "INCOMPLETE" if missing_docs or issues else "COMPLETE",
    }
