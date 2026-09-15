FROM python:3.12-slim

# Sem bytecode em disco e com stdout sem buffer (logs aparecem na hora).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config.py .
COPY scripts/ ./scripts/

EXPOSE 5050

CMD ["gunicorn", "-b", "0.0.0.0:5050", "--workers", "2", "--threads", "4", "app:create_app()"]
