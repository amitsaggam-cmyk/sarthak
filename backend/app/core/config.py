from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or `.env`."""

    app_name: str = "HR Background Verification API"
    app_version: str = "1.0.0"
    app_description: str = "AI Powered HR Background Verification System"
    database_url: str = "sqlite:///app/data/hr_mailbox.sqlite3"
    employee_data_path: str = "app/data/employees.json"
    email_file_path: str = "app/data/emails.json"
    llm_provider: str = "llama"
    llm_base_url: str = "http://localhost:8001/v1"
    llm_api_key: str = "your_api_key"
    llm_model: str = "your_model_name"
    llama_base_url: str = "https://aimodels.jadeglobal.com:8082/ollama/api"
    llama_model: str = "llama3.1:8b"
    llama_verify_ssl: bool = False
    mail_provider: str = "MOCK"
    mail_poll_interval: int = 5
    mail_processing_batch_size: int = 5
    email_source: str = "file"
    enable_background_ingestion: bool = False
    enable_background_processing: bool = False
    gmail_imap_host: str = "imap.gmail.com"
    gmail_imap_port: int = 993
    gmail_imap_username: str = ""
    gmail_imap_password: str = ""
    gmail_imap_mailbox: str = "INBOX"
    gmail_imap_search_criteria: str = "UNSEEN"
    gmail_attachment_dir: str = "app/data/attachments"
    workday_raas_url: str = ""
    workday_raas_username: str = ""
    workday_raas_password: str = ""
    workday_raas_verify_ssl: bool = True
    workday_lookup_param: str = "employee_name"
    workday_employee_id_field: str = "employee_id"
    workday_employee_name_field: str = "employee_name"
    workday_date_of_joining_field: str = "date_of_joining"
    workday_last_working_day_field: str = "last_working_day"
    workday_raas_fields: str = "employee_name,date_of_joining,last_working_day"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    log_level: str = "INFO"
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_TOKEN_URL: str = "/api/auth/login"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def cors_origin_list(self) -> list[str]:
        """Return configured CORS origins as a clean list for FastAPI."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cache settings so every module reads the same configuration."""

    return Settings()
