from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.schedule_router import router as schedule_router

app = FastAPI(
    title="Cron Job Email Scheduler",
    description=(
        "A REST API to create and manage scheduled email notifications. "
        "Schedules are defined using standard cron expressions and executed "
        "automatically via Celery Beat + Celery Worker."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schedule_router, prefix="/api/schedules", tags=["Schedules"])


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
