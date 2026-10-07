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
from pydantic import BaseModel

from .firebase_client import init_firebase, get_db
from .outbox_relay import process_outbox_once, send_push_to_token

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


def _check_token(x_flush_token: str) -> None:
    if FLUSH_TOKEN and x_flush_token != FLUSH_TOKEN:
        raise HTTPException(status_code=403, detail="bad token")


@app.post("/flush")
def flush(x_flush_token: str = Header(default="")):
    _check_token(x_flush_token)
    n = process_outbox_once()
    return {"processed": n}


class TestPushRequest(BaseModel):
    token: str
    title: str = "Test"
    body: str = "test push from curl"


@app.post("/test_push")
def test_push(req: TestPushRequest, x_flush_token: str = Header(default="")):
    """Прямая отправка FCM на переданный токен, минуя БД. Для диагностики."""
    _check_token(x_flush_token)
    return send_push_to_token(req.token, req.title, req.body)


@app.get("/device_tokens")
def device_tokens(x_flush_token: str = Header(default="")):
    """Список токенов устройств из user-tokens (для диагностики)."""
    _check_token(x_flush_token)
    tokens = get_db().child("user-tokens").get() or {}
    return {uid: list(devs.values()) for uid, devs in tokens.items()}


@app.get("/debug_state")
def debug_state(x_flush_token: str = Header(default="")):
    """Состояние outbox: сколько сообщений и какие статусы (для диагностики)."""
    _check_token(x_flush_token)
    outbox = get_db().child("outbox").get() or {}
    summary = []
    for msg_id, msg in outbox.items():
        if not isinstance(msg, dict):
            continue
        summary.append({
            "id": msg_id,
            "to": msg.get("to"),
            "sent": msg.get("sent"),
            "skipped": msg.get("skipped"),
            "timestamp": msg.get("timestamp"),
        })
    return {"count": len(summary), "messages": summary[-50:]}


def run_polling_loop(interval: int = 5) -> None:
    """Простой polling-режим: каждые N секунд проверяем outbox."""
    init_firebase()
    while True:
        try:
            process_outbox_once()
        except Exception as e:
            print(f"[relay] error: {e}")
        time.sleep(interval)
