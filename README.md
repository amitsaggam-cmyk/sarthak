# HR Background Verification Assistant

Local working model for automating HR background verification email review.

The app reads incoming verification requests, parses claimed employee details, compares only the allowed fields against a temporary Workday-like JSON file, and prepares a minimal safe reply for human approval.

## Current Setup

- Backend: FastAPI
- Frontend: React + Vite
- Current email source: local JSON file
- Optional future email sources: MySQL and Gmail
- Temporary Workday source: JSON file
- LLM provider config: Llama/Ollama-compatible endpoint

Current `.env` mode:

```env
EMAIL_SOURCE=file
EMAIL_FILE_PATH=app/data/emails.json
EMPLOYEE_DATA_PATH=app/data/employees.json
```

This means the app does not require MySQL on this laptop.

## Key Files

- Email inbox file: `backend/app/data/emails.json`
- Temporary Workday employee file: `backend/app/data/employees.json`
- Backend env: `backend/.env`
- Llama client: `backend/app/services/llm_client.py`
- Email source selector: `backend/app/services/email_source_factory.py`
- Frontend app: `frontend/src/main.jsx`

## Run Backend

```powershell
cd "D:\hr agent\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend API docs:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

## Run Frontend

```powershell
cd "D:\hr agent\frontend"
npm run dev -- --port 5174
```

Frontend:

```text
http://127.0.0.1:5174
```

If the page looks stale, hard refresh:

```text
Ctrl + Shift + R
```

## Demo Data

The file-backed inbox is:

```text
backend/app/data/emails.json
```

The app currently supports these email statuses:

```text
pending
reviewed
approved
rejected
```

The temporary Workday-like employee records are stored in:

```text
backend/app/data/employees.json
```

Only these fields are compared for verification:

```text
date_of_joining
last_working_day
```

The match rule is strict: even a one-day difference is flagged.

## LLM Connection Test

The configured Llama endpoint is read from:

```env
LLAMA_BASE_URL=https://aimodels.jadeglobal.com:8082/ollama/api
LLAMA_MODEL=llama3.1:8b
LLAMA_VERIFY_SSL=false
```

Test through the backend:

```powershell
curl -k -X POST "http://127.0.0.1:8000/api/llm/test" -H "Content-Type: application/json" -d "{\"prompt\":\"Hello from laptop\"}"
```

## Dummy File Workflow Test

This tests parsing and verification without the website:

```powershell
cd "D:\hr agent\backend"
.\.venv\Scripts\python.exe test_dummy_file.py
```

## Optional MySQL Mode

MySQL is not required for the current laptop demo. To use MySQL later, update `backend/.env`:

```env
EMAIL_SOURCE=database
DATABASE_URL=mysql+aiomysql://root:Sarthak0402@<mysql-host>:3306/hr_background_verification_db
```

Create the database:

```sql
CREATE DATABASE hr_background_verification_db;
```

Seed demo records into MySQL:

```powershell
cd "D:\hr agent\backend"
.\.venv\Scripts\python.exe seed_db.py
```

There is also a direct SQL seed file:

```text
backend/test_emails_seed.sql
```

## Optional Gmail Mode

Gmail is prepared as a future source but is not connected yet.

Future `.env` direction:

```env
EMAIL_SOURCE=gmail
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=
```

## Troubleshooting

If the frontend shows `Failed to fetch`, check that backend is running on port `8000`.

If the frontend shows `Backend API did not return JSON`, restart the frontend dev server and hard refresh the browser.

If MySQL mode shows `Database unavailable`, either start MySQL or switch back to:

```env
EMAIL_SOURCE=file
```
