"""Мгновенный worker: подписка на outbox через EventSource (Realtime DB streaming).
Запуск: python -m app.worker
Подходит для Fly.io / Render background worker — push приходит за <1 сек после записи."""
import time

from firebase_admin import db as rtdb

from .firebase_client import init_firebase
from .outbox_relay import process_outbox_once, send_push


def main() -> None:
    init_firebase()
    ref = rtdb.reference("outbox")
    print("[worker] listening to outbox ...")

    def on_child_added(context):
        # новый элемент в outbox — обрабатываем точечно
        event_path = context["path"].lstrip("/")
        msg_id = event_path.split("/")[-1] if event_path else None
        payload = context["data"] or {}
        if not msg_id or not isinstance(payload, dict):
            return
        _handle_single(msg_id, payload)

    def _handle_single(msg_id: str, msg: dict):
        if msg.get("sent"):
            return
        to_username = msg.get("to")
        from_uid = msg.get("fromId")
        if not to_username or not from_uid:
            ref.child(msg_id).update({"sent": True, "skipped": "malformed"})
            return
        root = rtdb.reference()
        user_node = root.child("users").order_by_child("username") \
            .equal_to(to_username).limit_to_first(1).get()
        recipient_uid = next(iter(user_node.keys())) if user_node else None
        if not recipient_uid:
            ref.child(msg_id).update({"sent": True, "skipped": "no-recipient"})
            return
        sent_ok = send_push(recipient_uid, msg)
        if sent_ok:
            root.child(f"user-messages/{recipient_uid}/{from_uid}/{msg_id}/delivered") \
                .set(True)
        ref.child(msg_id).update({"sent": True})

    ref.add_childEventListener("child_added", on_child_added)

    # fallback: раз в минуту полная проверка (на случай обрыва подписки)
    try:
        while True:
            time.sleep(60)
            process_outbox_once()
    except KeyboardInterrupt:
        print("[worker] stopped")


if __name__ == "__main__":
    main()
