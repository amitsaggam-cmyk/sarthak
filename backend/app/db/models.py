from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for SQLAlchemy database tables."""


class Email(Base):
    """Incoming verification email stored in MySQL."""
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    external_message_id: Mapped[str | None] = mapped_column(String(500), unique=True, nullable=True)
    
    # Claimed Details from Email
    claimed_candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claimed_employee_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claimed_nature_of_employment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claimed_start_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    claimed_end_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    claimed_last_designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claimed_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claimed_exit_formalities_completed: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Workday Details
    workday_candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workday_employee_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    workday_nature_of_employment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    workday_start_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workday_end_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workday_last_designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workday_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workday_exit_formalities_completed: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    field_results_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    all_fields_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="new",
    )
    processing_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class EmailAttachment(Base):
    """Attachment metadata and local file reference for an ingested email."""
    __tablename__ = "email_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class VerificationDecision(Base):
    """Human review decision stored before any external reply is sent."""
    __tablename__ = "verification_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class DocumentVerificationSubmission(Base):
    """Candidate document verification submission uploaded by HR."""
    __tablename__ = "document_verification_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PROCESSING",
    )
    pipeline_status_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_documents_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_documents_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DocumentVerificationFile(Base):
    """Uploaded file saved for a document verification submission."""
    __tablename__ = "document_verification_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("document_verification_submissions.id"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(700), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class User(Base):
    """Application user."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    password_reset_pin_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    password_reset_pin_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
    )
    module_access_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    @property
    def module_access(self) -> dict[str, str]:
        import json
        if self.role == "admin":
            return {"background_verification": "write", "document_verification": "write"}
        try:
            value = json.loads(self.module_access_json or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}


class UserManagementAudit(Base):
    """User management changes that need historical audit visibility."""
    __tablename__ = "user_management_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SUCCESS")
    details_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
