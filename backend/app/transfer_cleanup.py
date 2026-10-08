"""Чистильщик relay-зоны картинок (/transfers).

Политика (согласовано с клиентом, см. ChatLogActivity.writeMessage):
  - base64-тело картинки живёт в /transfers/<id> РОВНО 7 дней (поле expiresAt);
  - получатели скачивают тело в локальный кэш и пишут ACK deliveredTo/<uid>;
  - как только все адресаты из toIds скачали — data удаляется досрочно;
  - при истечении expiresAt — data удаляется принудительно (даже если никто
    не заходил), чтобы RTDB не раздувалась;
  - мёртвые записи (data уже удалена) стираются целиком через GRACE_SEC,
    ссылка transferRef в сообщении становится битой -> клиент покажет заглушку.

Запуск: python -m app.transfer_cleanup   (однократный проход)
или integrate_cron() внутри worker'а (каждый час).
"""
import time

from .firebase_client import get_db

GRACE_SEC = 3 * 24 * 3600  # 3 дня «аудита» после удаления тела, затем узел стирается


def _as_seconds(ts) -> int:
    """Клиент пишет timestamp в секундах; на всякий случай нормализуем миллисекунды."""
    ts = int(ts or 0)
    return ts // 1000 if ts >= 10_000_000_000 else ts


def cleanup_transfers_once(dry_run: bool = False) -> dict:
    """Один проход по /transfers. Возвращает счётчики действий."""
    ref = get_db()
    transfers = ref.child("transfers")
    try:
        items = transfers.get() or {}
    except Exception as e:
        code = getattr(getattr(e, "http_error", None), "code", None)
        if code == 404 or "404" in str(e):
            return {"checked": 0}
        raise

    now = int(time.time())
    stats = {"checked": 0, "early_cleaned": 0, "ttl_cleaned": 0, "deleted": 0, "errors": 0}

    for tid, t in items.items():
        if not isinstance(t, dict):
            continue
        stats["checked"] += 1
        try:
            has_data = bool(t.get("data"))

            if not has_data:
                # тело уже удалено — чистим метаданные по grace-периоду
                cleaned_at = _as_seconds(t.get("cleanedAt") or t.get("expiresAt") or 0)
                if cleaned_at and now - cleaned_at > GRACE_SEC:
                    if not dry_run:
                        transfers.child(tid).delete()
                    stats["deleted"] += 1
                continue

            expires_at = _as_seconds(t.get("expiresAt") or 0)
            delivered = t.get("deliveredTo") or {}
            to_ids = t.get("toIds") or [t.get("toId")] if isinstance(t.get("toId"), str) else (t.get("toIds") or [])
            recipients = {u for u in to_ids if u}

            ttl_expired = expires_at and now > expires_at
            all_downloaded = bool(recipients) and all(u in delivered for u in recipients)

            if ttl_expired or all_downloaded:
                if not dry_run:
                    transfers.child(tid).update({"data": None, "isCleanedUp": True, "cleanedAt": now})
                stats["ttl_cleaned" if ttl_expired else "early_cleaned"] += 1
        except Exception as e:
            print(f"[cleanup] transfer {tid}: {e}")
            stats["errors"] += 1

    if stats["ttl_cleaned"] or stats["early_cleaned"] or stats["deleted"]:
        print(f"[cleanup] {stats}")
    return stats


def integrate_cron(interval_sec: int = 3600) -> None:
    """Запускает очистку каждые interval_sec секунд в отдельном потоке (для worker'а)."""
    import threading

    def loop():
        while True:
            try:
                cleanup_transfers_once()
            except Exception as e:
                print(f"[cleanup] error: {e}")
            time.sleep(interval_sec)

    threading.Thread(target=loop, daemon=True).start()


if __name__ == "__main__":
    from .firebase_client import init_firebase

    init_firebase()
    print(cleanup_transfers_once())
