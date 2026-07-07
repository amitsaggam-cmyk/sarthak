from app.db.models import Base
from app.db.session import engine
from sqlalchemy import inspect, text


EMAIL_COLUMNS = {
    "external_message_id": "VARCHAR(500) NULL",
    "claimed_employee_name": "VARCHAR(255) NULL",
    "claimed_date_of_joining": "VARCHAR(50) NULL",
    "claimed_last_working_day": "VARCHAR(50) NULL",
    "workday_employee_name": "VARCHAR(255) NULL",
    "workday_date_of_joining": "VARCHAR(50) NULL",
    "workday_last_working_day": "VARCHAR(50) NULL",
    "field_results_json": "TEXT NULL",
    "all_fields_match": "BOOLEAN NULL",
    "processing_error": "TEXT NULL",
}

DECISION_COLUMNS = {
    "user_id": "INTEGER NULL",
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
    """Create MySQL tables required for the local demo if they do not exist."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_add_missing_columns, "emails", EMAIL_COLUMNS)
        await connection.run_sync(
            _add_missing_columns,
            "verification_decisions",
            DECISION_COLUMNS,
        )
