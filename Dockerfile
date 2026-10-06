FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app/ app/
# Режим релея задаётся переменной окружения на площадке:
#   worker  -> стриминг-подписка на outbox (Render background worker, Fly process)
#   web     -> FastAPI + внешний cron на POST /flush (Render free web service)
CMD ["sh", "-c", "if [ \"$MODE\" = \"worker\" ]; then python -m app.worker; else uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}; fi"]
