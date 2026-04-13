# iParish Church Management System – Backend

This is the backend of the iParish Church Management System built with **FastAPI**, **SQLAlchemy**, **PostgreSQL**, **Redis**, and **Celery**. It provides RESTful APIs to support authentication, member management, sacraments, collections, fundraising, and more.

---

## 🚀 Features

- JWT-based Authentication & Role Management
- Configurable Sacrament Handling with Certificate Generation
- MPesa Paybill Integration & Collection Tracking
- Fundraising Project Contributions
- Subscription Lifecycle for Parishes
- Celery-based Task Queue for Background Jobs
- PostgreSQL + Alembic for Database Migrations
- Dockerized for Local/Prod Deployment

---

## 🧱 Project Structure

```
├── api/                # All API route definitions
├── core/               # Celery config and background tasks
├── db/                 # Database models and session setup
├── schemas/            # Pydantic schemas for input/output
├── services/           # Business logic
├── utils/              # Helper functions/utilities
├── main.py             # FastAPI entry point
```

---

## ⚙️ Environment Setup

### 1. Clone the repo

````bash
git clone https://github.com/your-org/iparish-backend.git
cd iparish-backend


### 2. Set up environment

Create a `.env` file or configure environment variables for DB and Redis.

### 3. Start using Docker

```bash
docker-compose up --build
````

This starts:

- FastAPI server on `http://localhost:8000`
- PostgreSQL on `5432`
- Redis on `6379`
- Celery worker + beat scheduler

---

## 🔧 Development Tools

- Python 3.10+
- Uvicorn (dev server)
- Celery (background task queue)
- Alembic (DB migrations)
- Redis (message broker)

---

## 📬 API Documentation

Visit: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📥 Common Commands

```bash
# Run API without Docker (dev mode)
uvicorn main:app --reload

# Run Alembic migrations
alembic upgrade head

# Start Celery Worker
celery -A core.tasks worker --loglevel=info

# Start Celery Beat Scheduler
celery -A core.tasks beat --loglevel=info
```

---

## 🤝 Contributing

1. Create a new branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -am 'Add your feature'`
3. Push and create a PR

---

## 📝 License

MIT – Built and maintained by **BCK Kenya Ltd**.
