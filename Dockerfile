FROM python:3.11-slim

WORKDIR /app

# Install system packages (e.g., telnet, netcat for SMTP testing)
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    telnet \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "find . -type d -name '__pycache__' -exec rm -rf {} + && find . -type f -name '*.pyc' -delete && alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 ${ENV:+--reload}"]

