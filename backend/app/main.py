"""KotlinMassage backend — релей push-сообщений (outbox -> FCM).

Два режима:
  1. HTTP-сервис (FastAPI) — для деплоя на Render/Fly.io/PythonAnywhere:
       uvicorn app.main:app --host 0.0.0.0 --port $PORT
     эндпоинты:
       GET  /health          — проверка живости
       POST /flush           — немедленная обработка outbox (можно гонять cron'ом)
       WS   /firestore-like  — не используется; вместо этого Realtime DB push через клиента
  2. Worker (python -m app.worker) — долгоживущий процесс с подпиской на outbox
     (мгновенная реакция, без поллинга). Идеально для Fly.io/Render background worker.

Оба режима используют Admin SDK, поэтому правила безопасности остаются жёсткими:
клиент пишет в outbox как пользователь, а фактическую отправку делает сервер.
"""
import os
import threading
import time

from fastapi import FastAPI, Header, HTTPException

from .firebase_client import init_firebase
from .outbox_relay import process_outbox_once

app = FastAPI(title="KotlinMassage Push Relay")

# секрета у клиента нет — Admin SDK сам подписывает запросы;
# но /flush защищён токеном, чтобы им не злоупотребляли
FLUSH_TOKEN = os.environ.get("FLUSH_TOKEN", "")


@app.on_event("startup")
def startup() -> None:
    init_firebase()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/flush")
def flush(x_flush_token: str = Header(default="")):
    if FLUSH_TOKEN and x_flush_token != FLUSH_TOKEN:
        raise HTTPException(status_code=403, detail="bad token")
    n = process_outbox_once()
    return {"processed": n}


def run_polling_loop(interval: int = 5) -> None:
    """Простой polling-режим: каждые N секунд проверяем outbox."""
    init_firebase()
    while True:
        try:
            process_outbox_once()
        except Exception as e:
            print(f"[relay] error: {e}")
        time.sleep(interval)
