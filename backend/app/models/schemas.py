from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class EmailStatus(str, Enum):
    """Allowed processing states for an incoming HR verification email."""

    pending = "pending"
    reviewed = "reviewed"
    approved = "approved"
    rejected = "rejected"

class ProcessingStatus(str, Enum):
    """Progress of an email through the HR review workflow."""

    new = "new"
    pending = "pending"
    completed = "completed"

class DecisionValue(str, Enum):
    """Allowed human review outcomes."""

    approve_reply = "approve_reply"
    reject_reply = "reject_reply"


class EmailSummaryResponse(BaseModel):
    """Small email summary used by the inbox table."""

    id: int
    sender: str
    subject: str

    status: EmailStatus
    processing_status: ProcessingStatus

    received_at: datetime


class ClaimedEmployeeDetails(BaseModel):
    """Details parsed from the requesting company's email."""

    employee_id: str | None = None
    employee_name: str | None = None
    date_of_joining: date | None = None
    last_working_day: date | None = None


class WorkdayEmployeeDetails(BaseModel):
    """Limited demo employee data loaded from the temporary Workday JSON file."""

    employee_id: str | None = None
    employee_name: str | None = None
    date_of_joining: date | None = None
    last_working_day: date | None = None


class AttachmentResponse(BaseModel):
    """Attachment metadata shown in the review UI."""

    id: int
    filename: str
    content_type: str | None = None
    size_bytes: int


class FieldMatchResult(BaseModel):
    """Exact-match result for a single verification field."""

    field: str
    claimed_value: str | None
    workday_value: str | None
    matches: bool


class VerificationResponse(BaseModel):
    """Full review payload for the internal HR dashboard."""

    email_id: int
    sender: str
    subject: str
    body: str
    claimed_details: ClaimedEmployeeDetails
    workday_details: WorkdayEmployeeDetails | None
    field_results: list[FieldMatchResult]
    all_fields_match: bool
    recommended_reply: str
    attachments: list[AttachmentResponse] = []


class SafeReplyResponse(BaseModel):
    """Minimal outbound reply preview that avoids leaking employee details."""

    email_id: int
    reply_to: str
    subject: str
    body: str


class DecisionRequest(BaseModel):
    """Human approval or rejection request for a prepared verification reply."""

    decision: DecisionValue
    note: str | None = Field(default=None, max_length=500)


class DecisionResponse(BaseModel):
    """Confirmation returned after a human decision is stored."""

    email_id: int
    decision: DecisionValue
    message: str


class DecisionLogResponse(BaseModel):
    """Audit row showing which HR user handled an email."""

    id: int
    email_id: int
    email_subject: str
    user_full_name: str | None = None
    user_email: str | None = None
    decision: DecisionValue
    note: str | None = None
    decided_at: datetime


class LlmTestRequest(BaseModel):
    """Prompt used to test the configured Llama/Ollama-compatible API."""

    prompt: str = Field(default="Hello from laptop", max_length=1000)


class LlmTestResponse(BaseModel):
    """Small connection-test result from the configured LLM provider."""

    provider: str
    model: str
    success: bool
    message: str
