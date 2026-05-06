# Cron Job Email Scheduler

A self-contained REST API that lets you create, manage, and trigger **scheduled email notifications** using cron expressions. Built with **FastAPI**, **Celery Beat**, **Redis**, and **PostgreSQL** — all wired up with **Docker Compose**.

---

## Features

- Create scheduled email jobs with any standard 5-part cron expression
- Custom recipient, subject, and message per job
- Activate / deactivate schedules without deleting them
- Manually trigger any schedule on demand via the API
- Auto-calculated `next_run_at` on create and after every send
- Celery Flower dashboard for real-time task monitoring
- Swagger UI at `/docs` and ReDoc at `/redoc`

---

## Architecture

```
┌──────────────┐        REST API        ┌────────────────────┐
│   Client /   │ ─────────────────────► │  FastAPI (web)      │
│   Swagger    │                        │  :8000              │
└──────────────┘                        └────────┬───────────┘
                                                 │  reads/writes
                                          ┌──────▼──────┐
                                          │  PostgreSQL  │
                                          │  :5433       │
                                          └──────────────┘

┌──────────────────┐   every minute   ┌──────────────────────┐
│  Celery Beat     │ ───────────────► │  Celery Worker        │
│  (scheduler)     │                  │  sends emails via SMTP│
└──────────────────┘                  └──────────────────────┘
        │                                       │
        └──────────────────────────────────────►│
                      Redis (broker)

┌──────────────────┐
│  Flower           │  http://localhost:5555
│  (monitoring)     │
└──────────────────┘
```

**How scheduling works:**

1. Celery Beat triggers `dispatch_scheduled_emails` every minute.
2. That task queries all **active** jobs whose `next_run_at ≤ now`.
3. For each due job it dispatches `send_scheduled_email` to a worker and advances `next_run_at` to the next occurrence.
4. The worker sends the email via SMTP and records `last_run_at`.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Docker | 24+ |
| Docker Compose | v2 |

No local Python installation required — everything runs inside containers.

---

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd cron-job-scheduler-with-email-notification

cp .env.example .env
```

Open `.env` and fill in your SMTP credentials (see [Email Setup](#email-setup)).

### 2. Build and start all services

```bash
docker compose up --build
```

Services started:

| Container | Port | Purpose |
|-----------|------|---------|
| `cron_scheduler_web` | 8000 | FastAPI REST API |
| `cron_scheduler_worker` | — | Celery email worker |
| `cron_scheduler_beat` | — | Celery cron dispatcher |
| `cron_scheduler_flower` | 5555 | Task monitoring UI |
| `cron_scheduler_redis` | 6379 | Message broker |
| `cron_scheduler_db` | 5433 | PostgreSQL database |

### 3. Open the API

- Swagger UI → [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc → [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health check → [http://localhost:8000/health](http://localhost:8000/health)
- Flower → [http://localhost:5555](http://localhost:5555)

---

## Email Setup

The app sends email over SMTP with TLS (port 587). Gmail is the default provider.

### Gmail (recommended for testing)

1. Enable 2-Step Verification on your Google account.
2. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) and create an App Password for **Mail**.
3. Set in `.env`:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=you@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx   # the 16-char app password
```

### Other providers

| Provider | SMTP_SERVER | SMTP_PORT |
|----------|-------------|-----------|
| Outlook / Hotmail | smtp.office365.com | 587 |
| Yahoo | smtp.mail.yahoo.com | 587 |
| SendGrid | smtp.sendgrid.net | 587 |
| Mailgun | smtp.mailgun.org | 587 |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `development` | App environment; enables `--reload` in dev |
| `DATABASE_URL` | `postgresql+psycopg2://fastapi_user:fastapi_password@db:5432/fastapi_db` | PostgreSQL connection string |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Redis broker URL |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` | Redis result backend URL |
| `SMTP_SERVER` | `smtp.gmail.com` | SMTP host |
| `SMTP_PORT` | `587` | SMTP port |
| `EMAIL_USER` | *(required)* | Sender email address |
| `EMAIL_PASSWORD` | *(required)* | SMTP password / app password |

---

## API Reference

Base URL: `http://localhost:8000`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/schedules/` | Create a new schedule |
| `GET` | `/api/schedules/` | List all schedules |
| `GET` | `/api/schedules/{id}` | Get a single schedule |
| `PUT` | `/api/schedules/{id}` | Update a schedule |
| `DELETE` | `/api/schedules/{id}` | Delete a schedule |
| `POST` | `/api/schedules/{id}/trigger` | Manually send the email now |

### Create a schedule — `POST /api/schedules/`

**Request body:**

```json
{
  "name": "Daily Morning Report",
  "recipient_email": "alice@example.com",
  "subject": "Good morning!",
  "message": "Here is your daily briefing for today.",
  "cron_expression": "0 8 * * *",
  "timezone": "UTC",
  "is_active": true
}
```

**Response `201`:**

```json
{
  "id": 1,
  "name": "Daily Morning Report",
  "recipient_email": "alice@example.com",
  "subject": "Good morning!",
  "message": "Here is your daily briefing for today.",
  "cron_expression": "0 8 * * *",
  "timezone": "UTC",
  "is_active": true,
  "created_at": "2026-05-06T10:00:00Z",
  "last_run_at": null,
  "next_run_at": "2026-05-07T08:00:00Z"
}
```

### Cron Expression Reference

A cron expression has five fields separated by spaces:

```
┌───── minute        (0–59)
│ ┌─── hour          (0–23)
│ │ ┌─ day of month  (1–31)
│ │ │ ┌ month        (1–12)
│ │ │ │ ┌ day of week (0–6, 0=Sunday)
│ │ │ │ │
* * * * *
```

**Common examples:**

| Expression | Meaning |
|------------|---------|
| `* * * * *` | Every minute |
| `0 * * * *` | Every hour (on the hour) |
| `0 8 * * *` | Every day at 08:00 UTC |
| `0 8 * * 1` | Every Monday at 08:00 UTC |
| `0 9 1 * *` | First day of every month at 09:00 UTC |
| `*/30 * * * *` | Every 30 minutes |
| `0 8,17 * * 1-5` | Weekdays at 08:00 and 17:00 UTC |

---

## Usage Examples

### Create a schedule (curl)

```bash
curl -X POST http://localhost:8000/api/schedules/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekly Summary",
    "recipient_email": "bob@example.com",
    "subject": "Weekly update",
    "message": "Here is your weekly summary.",
    "cron_expression": "0 9 * * 1"
  }'
```

### List all schedules

```bash
curl http://localhost:8000/api/schedules/
```

### Manually trigger a schedule

```bash
curl -X POST http://localhost:8000/api/schedules/1/trigger
```

### Pause a schedule

```bash
curl -X PUT http://localhost:8000/api/schedules/1 \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

### Delete a schedule

```bash
curl -X DELETE http://localhost:8000/api/schedules/1
```

---

## Monitoring with Flower

Open [http://localhost:5555](http://localhost:5555) to see:

- Active, reserved, and completed tasks
- Worker status and concurrency
- Task history and failure details
- Real-time task throughput

---

## Project Structure

```
.
├── api/
│   └── schedule_router.py      # CRUD + trigger endpoints
├── core/
│   ├── celery_app.py           # Celery app + beat schedule
│   └── tasks.py                # dispatcher & send tasks
├── db/
│   ├── base_class.py           # SQLAlchemy declarative Base
│   ├── session.py              # engine + session factory
│   └── models/
│       └── scheduled_email.py  # ScheduledEmail ORM model
├── schemas/
│   └── scheduled_email_schema.py  # Pydantic request/response schemas
├── utils/
│   └── email_client.py         # SMTP email sender
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_create_scheduled_emails.py
├── .env.example
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Development

### Run without Docker (local venv)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Postgres and Redis locally first, then:
alembic upgrade head
uvicorn main:app --reload
celery -A core.celery_app worker --loglevel=info
celery -A core.celery_app beat --loglevel=info
```

### Useful Docker commands

```bash
# View logs for a specific service
docker compose logs -f celery_worker

# Restart only the beat scheduler
docker compose restart celery_beat

# Stop everything and remove volumes
docker compose down -v

# Rebuild images after code changes
docker compose up --build
```

### Apply a new migration

```bash
docker compose exec web alembic revision --autogenerate -m "describe change"
docker compose exec web alembic upgrade head
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Emails not sending | Check `EMAIL_USER` / `EMAIL_PASSWORD` in `.env`; verify the App Password |
| `SMTPAuthenticationError` | Use an App Password, not your account password |
| Schedules not triggering | Check `celery_beat` logs: `docker compose logs -f celery_beat` |
| Worker not picking up tasks | Check Redis connectivity and `celery_worker` logs |
| DB connection refused | Wait for `db` container to pass its health check |
