"""Релей read-receipt: /chat-read-status/{chatId}/{readerUid} -> .../mirror.

Клиент (Android) пишет receipt только в СВОЙ узел — правила RTDB разрешают это
без admin-прав. Но собеседник по тем же правилам НЕ может прочитать чужой узел
статуса. Поэтому релей (Admin SDK, обходит правила) копирует receipt в
зеркалированный узел того же диалога:

    /chat-read-status/{chatId}/{readerUid}/mirror = {ts, msgId, by}

Клиент-отправитель слушает mirror собеседника (DbPaths.chatReadMirror):
правила БД разрешают читать mirror_* всем участникам, кроме самого читателя,
и писать его может только релей (.write: false для клиентов). Один маленький
узел на участника вместо реворка сообщений — дёшево по лимитам RTDB.

Источники пар участников:
  1. chatId из ключа узла status (детерминированный sortedChatId = min|max uid);
  2. users/<uid>/username -> latest-messages/<username>/<peerUsername>/uid
     (то же дерево, что уже использует outbox-релей для поиска получателя).
"""
import time

from .firebase_client import get_db



def _as_seconds(ts) -> int:
    ts = int(ts or 0)
    return ts // 1000 if ts >= 10_000_000_000 else ts


def _peers_from_chat_id(chat_id: str) -> tuple[str, str] | None:
    """sortedChatId клиента (DbPaths.kt) = 'minUid_maxUid' -> обе стороны.

    Firebase uid не содержит подчёркиваний; если формат вдруг другой —
    возвращаем None и партнёров найдём через latest-messages."""
    parts = chat_id.split("_")
    if len(parts) == 2 and all(parts):
        return parts[0], parts[1]
    return None


def _resolve_peers(ref, reader_uid: str) -> list[str]:
    """Список uid собеседников читателя через latest-messages (username-дерево)."""
    peers: list[str] = []
    try:
        user = ref.child("users").child(reader_uid).get() or {}
    except Exception:
        return peers
    username = user.get("username") if isinstance(user, dict) else None
    if not username:
        return peers
    try:
        chats = ref.child("latest-messages").child(username).get() or {}
    except Exception:
        return peers
    for peer_name, node in chats.items():
        if not isinstance(node, dict):
            continue
        uid = node.get("uid")
        if uid and uid != reader_uid:
            peers.append(uid)
    return peers


def _mirror_receipt(statuses, chat_id: str, reader_uid: str,
                     receipt: dict, has_peer: bool) -> tuple[int, int, int]:
    """Обновить /chat-read-status/{chatId}/{readerUid}/mirror одним свежайшим
    receipt'ом читателя. has_peer — есть ли в диалоге вторая сторона.
    Возвращает (записано, пропущено, ошибки)."""
    if not has_peer:
        return 0, 0, 0
    ts = _as_seconds(receipt.get("ts"))
    if ts <= 0 or not receipt.get("msgId"):
        return 0, 0, 0
    mpath = f"{chat_id}/{reader_uid}/mirror"
    try:
        cur = statuses.child(chat_id).child(reader_uid).child("mirror").get()
    except Exception:
        cur = None
    # зеркало обновляем только если прилетел более свежий receipt
    if isinstance(cur, dict) and _as_seconds(cur.get("ts")) >= ts:
        return 0, 1, 0
    payload = {"ts": receipt.get("ts"), "msgId": receipt.get("msgId"), "by": reader_uid}
    try:
        statuses.child(chat_id).child(reader_uid).child("mirror").update(payload)
        return 1, 0, 0
    except Exception as e:
        print(f"[read-relay] mirror write failed {mpath}: {e}")
        return 0, 0, 1


def mirror_receipt(chat_id: str, reader_uid: str, receipt: dict) -> int:
    """Точечное зеркало одного receipt'а (worker на child_added/changed).
    Возвращает число обновлённых зеркал."""
    ref = get_db()
    peers = [p for p in (_peers_from_chat_id(chat_id) or ()) if p != reader_uid]
    has_peer = bool(peers) or bool(_resolve_peers(ref, reader_uid))
    written, _, _ = _mirror_receipt(
        ref.child("chat-read-status"), chat_id, reader_uid, receipt, has_peer)
    return written


def process_read_status_once(max_age_seconds: int = 7 * 86400) -> dict:
    """Один проход по /chat-read-status. Возвращает счётчики действий."""
    ref = get_db()
    statuses = ref.child("chat-read-status")
    try:
        chats = statuses.get() or {}
    except Exception as e:
        code = getattr(getattr(e, "http_error", None), "code", None)
        if code == 404 or "404" in str(e):
            return {"checked": 0, "mirrored": 0, "skipped_fresh": 0,
                    "no-peer": 0, "expired": 0, "errors": 0}
        raise

    now_ms = int(time.time() * 1000)
    stats = {"checked": 0, "mirrored": 0, "skipped_fresh": 0,
             "no-peer": 0, "expired": 0, "errors": 0}
    mirrored_total = 0

    for chat_id, nodes in chats.items():
        if not isinstance(nodes, dict):
            continue
        from_key = _peers_from_chat_id(chat_id)
        for reader_uid, receipt in nodes.items():
            if not isinstance(receipt, dict):
                continue
            # узел читателя содержит служебное зеркало "mirror" — сам receipt в полях ts/msgId
            if receipt.get("msgId") is None and "mirror" in receipt:
                continue
            stats["checked"] += 1
            msg_id = receipt.get("msgId")
            ts = _as_seconds(receipt.get("ts")) * 1000
            if not msg_id or ts <= 0:
                continue
            if now_ms - ts > max_age_seconds * 1000:
                stats["expired"] += 1
                continue

            # есть ли у диалога вторая сторона (из ключа chatId или latest-messages)
            peers = [p for p in (from_key or ()) if p != reader_uid]
            has_peer = bool(peers) or bool(_resolve_peers(ref, reader_uid))
            if not has_peer:
                stats["no-peer"] += 1
                continue

            written, skipped, errs = _mirror_receipt(statuses, chat_id, reader_uid, receipt, has_peer)
            stats["mirrored"] += written
            stats["skipped_fresh"] += skipped
            stats["errors"] += errs
            mirrored_total += written

    return stats


def integrate_cron(interval_sec: int = 60) -> None:
    """Фоновый поток: релей статусов раз в минуту (как и cron /flush)."""
    import threading

    def loop():
        while True:
            try:
                st = process_read_status_once()
                if st["mirrored"]:
                    print(f"[read-relay] {st}")
            except Exception as e:
                print(f"[read-relay] error: {e}")
            time.sleep(interval_sec)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
