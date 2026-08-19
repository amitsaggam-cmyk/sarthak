from functools import lru_cache


from pydantic_settings import BaseSettings, SettingsConfigDict




class Settings(BaseSettings):
    """Application settings loaded from environment variables or `.env`."""


    app_name: str = "JADE HR Background Verification API"
    app_version: str = "1.0.0"
    app_description: str = "AI Powered JADE HR Background Verification System"
    app_base_url: str = "http://localhost:5173"
    database_url: str = "sqlite+aiosqlite:///app/data/hr_mailbox.sqlite3"
    employee_data_path: str = "app/data/employees.json"
    email_file_path: str = "app/data/emails.json"
    llm_provider: str = "azure_openai"
    llm_base_url: str = "http://localhost:8001/v1"
    llm_api_key: str = "your_api_key"
    llm_model: str = "your_model_name"
    llama_base_url: str = "https://aimodels.jadeglobal.com:8082/ollama/api"
    llama_model: str = "llama3.1:8b"
    llama_username: str = ""
    llama_password: str = ""
    llama_verify_ssl: bool = False
    mail_provider: str = "GMAIL"
    mail_poll_interval: int = 5
    mail_processing_batch_size: int = 5
    email_source: str = "gmail"
    enable_background_ingestion: bool = True
    enable_background_processing: bool = True
    gmail_imap_host: str = "imap.gmail.com"
    gmail_imap_port: int = 993
    gmail_imap_username: str = ""
    gmail_imap_password: str = ""
    gmail_imap_mailbox: str = "INBOX"
    gmail_imap_search_criteria: str = "UNSEEN"
    gmail_attachment_dir: str = "app/data/attachments"
    workday_raas_url: str = "https://impl-services1.wd12.myworkday.com/ccx/service/customreport2/jadeglobal_dpt2/ISU_Employee_Verification/CR_Employee_Verification_Automation"
    workday_raas_username: str = "ISU_Employee_Verification"
    workday_raas_password: str = ""
    workday_raas_verify_ssl: bool = True
    workday_lookup_param: str = "employee_id"
    workday_employee_id_field: str = "employee_id"
    workday_employee_name_field: str = "candidate_name"
    workday_nature_of_employment_field: str = "nature_of_employment"
    workday_start_date_field: str = "start_date"
    workday_end_date_field: str = "end_date"
    workday_last_designation_field: str = "last_designation"
    workday_location_field: str = "location"
    workday_exit_formalities_completed_field: str = "exit_formalities_completed"
    workday_raas_fields: str = "employee_id,candidate_name,nature_of_employment,start_date,end_date,last_designation,location,exit_formalities_completed"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    log_level: str = "INFO"
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 1440
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_TOKEN_URL: str = "/api/auth/login"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    doc_verification_upload_dir: str = "app/data/doc_verification_uploads"
    doc_verification_max_files: int = 80
    doc_verification_max_file_size_mb: int = 80
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment: str = "ilabs-gpt-5-mini"
    doc_verification_pipeline_concurrency: int = 4
    google_drive_service_account_file: str = ""
    google_drive_service_account_json: str = ""


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


    def cors_origin_list(self) -> list[str]:
        """Return configured CORS origins as a clean list for FastAPI."""


        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]




@lru_cache
def get_settings() -> Settings:
    """Cache settings so every module reads the same configuration."""


    return Settings()
