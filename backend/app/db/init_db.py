from app.db.models import Base
from app.db.session import engine
from sqlalchemy import inspect, text

EMAIL_COLUMNS = {
    "status": "VARCHAR(50) NOT NULL DEFAULT 'new'",
    "processing_status": "VARCHAR(20) NOT NULL DEFAULT 'new'",
    "received_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "external_message_id": "VARCHAR(500) NULL",
    
    # Claimed Details from Email
    "claimed_candidate_name": "VARCHAR(255) NULL",
    "claimed_employee_id": "VARCHAR(100) NULL",
    "claimed_nature_of_employment": "VARCHAR(100) NULL",
    "claimed_start_date": "VARCHAR(50) NULL",
    "claimed_end_date": "VARCHAR(50) NULL",
    "claimed_last_designation": "VARCHAR(255) NULL",
    "claimed_location": "VARCHAR(255) NULL",
    "claimed_exit_formalities_completed": "VARCHAR(50) NULL",
    
    # Workday Details
    "workday_candidate_name": "VARCHAR(255) NULL",
    "workday_employee_id": "VARCHAR(100) NULL",
    "workday_nature_of_employment": "VARCHAR(100) NULL",
    "workday_start_date": "VARCHAR(50) NULL",
    "workday_end_date": "VARCHAR(50) NULL",
    "workday_last_designation": "VARCHAR(255) NULL",
    "workday_location": "VARCHAR(255) NULL",
    "workday_exit_formalities_completed": "VARCHAR(50) NULL",
    
    "field_results_json": "TEXT NULL",
    "all_fields_match": "BOOLEAN NULL",
    "processing_error": "TEXT NULL",
}

DECISION_COLUMNS = {
    "user_id": "INTEGER NULL",
    "sent_reply": "TEXT NULL",
}

USER_COLUMNS = {
    "role": "VARCHAR(20) NOT NULL DEFAULT 'user'",
    "module_access_json": "TEXT NULL",
    "password_reset_pin_hash": "VARCHAR(255) NULL",
    "password_reset_pin_expires_at": "TIMESTAMP NULL",
}

DOCUMENT_VERIFICATION_SUBMISSION_COLUMNS = {
    "revision": "INTEGER NOT NULL DEFAULT 1",
    "manual_changes_json": "TEXT NULL",
}

def _add_missing_columns(sync_connection, table_name: str, columns: dict[str, str]) -> None:
    inspector = inspect(sync_connection)
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    for column_name, column_type in columns.items():
        if column_name in existing:
            continue
        sync_connection.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        )

async def initialize_database() -> None:
    """Create database tables if they do not exist."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_add_missing_columns, "emails", EMAIL_COLUMNS)
        await connection.run_sync(
            _add_missing_columns,
            "verification_decisions",
            DECISION_COLUMNS,
        )
        await connection.run_sync(
            _add_missing_columns,
            "users",
            USER_COLUMNS,
        )
        await connection.run_sync(
            _add_missing_columns,
            "document_verification_submissions",
            DOCUMENT_VERIFICATION_SUBMISSION_COLUMNS,
        )
