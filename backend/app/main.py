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
from .read_relay import process_read_status_once
from .transfer_cleanup import cleanup_transfers_once

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
    # read-receipt релей гоняем тем же cron-ударом: дёшево и без второго расписания
    read_stats = None
    try:
        read_stats = process_read_status_once()
    except Exception as e:
        print(f"[flush] read-relay error: {e}")
    n = process_outbox_once()
    # last_report — что произошло с КАЖДЫМ unsent-сообщением за этот проход:
    # sent / NO_TOKENS_OR_SEND_FAILED / no-recipient / expired / malformed
    return {"processed": n,
            "report": getattr(process_outbox_once, "last_report", []),
            "read_relay": read_stats}


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
    try:
        tokens = get_db().child("user-tokens").get() or {}
    except Exception:
        tokens = {}  # узла ещё нет в БД — это не ошибка
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


@app.post("/inspect_outbox")
@app.get("/inspect_outbox")
def inspect_outbox(x_flush_token: str = Header(default="")):
    """Диагностика цепочки push: outbox-сообщения, uid получателя по username,
    где лежат его токены. Показывает, на каком именно шаге всё ломается."""
    _check_token(x_flush_token)
    ref = get_db()
    try:
        outbox = ref.child("outbox").get() or {}
    except Exception:
        outbox = {}
    try:
        users = ref.child("users").get() or {}
    except Exception:
        users = {}
    by_name = {u.get("username"): uid for uid, u in users.items() if isinstance(u, dict)}
    report = []
    for msg_id, msg in list(outbox.items())[-10:]:
        if not isinstance(msg, dict):
            continue
        to_username = msg.get("to")
        r_uid = by_name.get(to_username)
        tokens_info = "recipient uid not found"
        token_sources = []
        if r_uid:
            try:
                ut = ref.child("user-tokens").child(r_uid).get()
                if ut:
                    token_sources.append(("user-tokens", len(ut)))
            except Exception:
                pass
            try:
                uu = ref.child("users").child(r_uid).get() or {}
                if uu.get("newToken"):
                    token_sources.append(("users/newToken", 1))
            except Exception:
                pass
            if not token_sources:
                token_sources.append(("NO TOKENS ANYWHERE", 0))
        report.append({
            "id": msg_id,
            "to": to_username,
            "recipient_uid": r_uid,
            "sent": msg.get("sent"),
            "skipped": msg.get("skipped"),
            "timestamp": msg.get("timestamp"),
            "token_sources": token_sources,
        })
    return {"pending_or_recent": report}



@app.post("/flush_read_status")
def flush_read_status(x_flush_token: str = Header(default="")):
    """Релей read-receipt: копирует /chat-read-status/{chatId}/{readerUid}
    в mirror_{peerUid} того же диалога (клиент-отправитель слушает зеркало)."""
    _check_token(x_flush_token)
    return process_read_status_once()


@app.get("/debug_read_status")
def debug_read_status(x_flush_token: str = Header(default="")):
    """Состояние зоны статусов прочтения (для диагностики галочек)."""
    _check_token(x_flush_token)
    try:
        raw = get_db().child("chat-read-status").get() or {}
    except Exception:
        raw = {}
    out = []
    for chat_id, nodes in list(raw.items())[-20:]:
        if isinstance(nodes, dict):
            out.append({"chatId": chat_id, "nodes": {k: v for k, v in nodes.items()}})
    return {"chats": len(out), "detail": out}


@app.post("/cleanup_transfers")
def cleanup_transfers(x_flush_token: str = Header(default="")):
    """Автоочистка relay-зоны картинок /transfers (TTL 7 дней или все скачали).
    Гонять cron'ом раз в час."""
    if FLUSH_TOKEN and x_flush_token != FLUSH_TOKEN:
        raise HTTPException(status_code=403, detail="bad token")
    return cleanup_transfers_once()

def run_polling_loop(interval: int = 5) -> None:
    """Простой polling-режим: каждые N секунд проверяем outbox."""
    init_firebase()
    while True:
        try:
            process_outbox_once()
        except Exception as e:
            print(f"[relay] error: {e}")
        time.sleep(interval)
