"""Релей outbox -> FCM: читает новые исходящие сообщения из outbox,
отправляет push получателю и помечает сообщение доставленным."""
import time

from .firebase_client import get_db


def _get_recipient_uids(ref) -> list[str]:
    """Список всех uid пользователей (для поиска по username получателя)."""
    users = ref.child("users").get() or {}
    return list(users.keys())


def process_outbox_once(max_age_seconds: int = 3600) -> int:
    """Один проход по outbox. Возвращает количество обработанных сообщений."""
    ref = get_db()
    outbox = ref.child("outbox")
    try:
        pending = outbox.get(shallow=False) or {}
    except Exception as e:
        # если узла outbox ещё нет в базе (клиент ничего не писал) — не ошибка,
        # а просто нечего обрабатывать; Firebase REST отдаёт 404 на несуществующий путь
        code = getattr(getattr(e, "http_error", None), "code", None)
        if code == 404 or "404" in str(e):
            return 0
        raise

    processed = 0
    now_ms = int(time.time() * 1000)

    for msg_id, msg in pending.items():
        if not isinstance(msg, dict):
            continue
        if msg.get("sent"):
            continue
        ts = msg.get("timestamp") or 0
        # клиент пишет timestamp в СЕКУНДАХ (System.currentTimeMillis()/1000) —
        # нормализуем к миллисекундам, иначе любое живое сообщение считалось
        # "протухшим" и молча помечалось skipped=expired без отправки пуша
        if ts < 10_000_000_000:
            ts *= 1000
        if now_ms - ts > max_age_seconds * 1000:
            outbox.child(msg_id).update({"sent": True, "skipped": "expired"})
            continue

        to_username = msg.get("to")
        from_uid = msg.get("fromId")
        if not to_username or not from_uid:
            outbox.child(msg_id).update({"sent": True, "skipped": "malformed"})
            continue

        # находим uid получателя по username
        recipient_uid = None
        user_node = ref.child("users").order_by_child("username") \
            .equal_to(to_username).limit_to_first(1).get()
        if user_node:
            recipient_uid = next(iter(user_node.keys()))
        if not recipient_uid:
            # помечаем: пользователь не найден, повторять бессмысленно
            outbox.child(msg_id).update({"sent": True, "skipped": "no-recipient"})
            continue

        sent_ok = send_push(recipient_uid, msg)

        # записываем статус в зеркало собеседника, чтобы клиент видел "доставлено"
        status_path = f"user-messages/{recipient_uid}/{from_uid}/{msg_id}/delivered"
        try:
            if sent_ok:
                ref.child(status_path).set(True)
        except Exception:
            pass
        outbox.child(msg_id).update({"sent": True})
        processed += 1

    return processed


def send_push(recipient_uid: str, msg: dict) -> bool:
    """Отправка FCM на все токены получателя. Возвращает True, если хотя бы один доставлен."""
    from firebase_admin import messaging

    tokens_ref = get_db().child("user-tokens").child(recipient_uid)
    tokens = tokens_ref.get() or {}
    if not tokens:
        return False

    # в базе поле текста называется text (см. model/ChatMessage.kt)
    body = msg.get("preview") or msg.get("text") or msg.get("message") or ""
    if msg.get("msgType") == "IMAGE":
        body = "📷 Фото"
    title = msg.get("senderName") or msg.get("username") or "Новое сообщение"

    registration_tokens = [t for t in tokens.values() if t]
    if not registration_tokens:
        return False

    response = messaging.send_each(
        [
            messaging.Message(
                token=t,
                notification=messaging.Notification(
                    title=title, body=body[:200]
                ),
                data={
                    "fromUid": msg.get("fromId", ""),
                    "fromUsername": title,
                    "msgId": str(msg.get("id", "")),
                    "image": "true" if msg.get("msgType") == "IMAGE" else "false",
                },
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        channel_id="chat"
                    ),
                ),
            )
            for t in registration_tokens
        ]
    )
    # чистим протухшие токены
    failed_indices = [
        i for i, r in enumerate(response.responses)
        if not r.success
    ]
    for i in failed_indices:
        did = list(tokens.keys())[i]
        err = str(response.responses[i].error)
        if "UNREGISTERED" in err or "INVALID_ARGUMENT" in err:
            tokens_ref.child(did).delete()

    return response.success_count > 0
