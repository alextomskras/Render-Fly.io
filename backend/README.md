# KotlinMassage Push Relay (backend)

Сервер-релей для отправки FCM push-уведомлений. Решает проблему прав доступа:
клиент пишет сообщение в `outbox/` (правила разрешают это авторизованному пользователю),
а бэкенд с **Firebase Admin SDK** читает outbox, отправляет push получателю и помечает
`delivered` в его зеркале переписки. Правила БД при этом остаются жёсткими —
`.read` для outbox может быть закрыт даже полностью (Admin SDK обходит правила).

## Почему не Cloudflare Workers
Для подписи JWT service account нужен RSA (`RS256`) — на воркерах это возможно, но
firebase-admin там недоступен, пришлось бы писать crypto вручную. Python + firebase-admin
надёжнее и дешевле в поддержке. Рекомендуемые бесплатные площадки:

| Площадка | Бесплатно | Долгоживущий процесс |
|---|---|---|
| **Fly.io** | да (3 VM) | ✅ worker-режим |
| Render | 750 ч | sleep на free plan → polling через cron-job.org |
| Railway | $5 кредит | ✅ |

## Структура
```
backend/
├── requirements.txt
└── app/
    ├── firebase_client.py   # инициализация Admin SDK
    ├── outbox_relay.py      # process_outbox_once + send_push
    ├── main.py              # FastAPI: GET /health, POST /flush
    └── worker.py            # мгновенный релей: слушает outbox через streaming
```

## Запуск локально
```bash
cd backend
pip install -r requirements.txt
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/serviceAccountKey.json
export FIREBASE_DATABASE_URL=https://kotlinmassage-default-rtdb.firebaseio.com

# вариант 1 — HTTP (для деплоя + внешнего cron):
uvicorn app.main:app --host 0.0.0.0 --port 8080

# вариант 2 — мгновенный worker (рекомендуется для Fly.io):
python -m app.worker
```

Service account key: Firebase Console → Project settings → Service accounts →
Generate new private key. **Никогда не коммитьте ключ в git.**

## Деплой на Fly.io (рекомендуемый путь)
```bash
fly launch --no-deploy        # создаст fly.toml (образ python)
fly secrets set FIREBASE_SERVICE_ACCOUNT='{"type":"service_account",...}' \
                FIREBASE_DATABASE_URL=https://kotlinmassage-default-rtdb.firebaseio.com
# в fly.toml: cmd = "python -m app.worker"
fly deploy
```

## Деплой на Render
- Web Service c `uvicorn app.main:app`, env `FIREBASE_SERVICE_ACCOUNT` (JSON-строкой)
- Free plan засыпает → добавить внешний cron (cron-job.org) на `POST /flush` каждые 1–2 мин
  с заголовком `X-Flush-Token: <FLUSH_TOKEN>`

## Клиент (Android) должен писать в outbox
При отправке сообщения, кроме атомарного updateChildren в user-messages/latest-messages,
добавить запись:
```kotlin
updates["outbox/$msgId"] = mapOf(
    "id" to msgId, "fromId" to myUid, "senderName" to myUsername,
    "to" to recipientUsername, "text" to text,
    "msgType" to if (isImage) "IMAGE" else "TEXT",
    "timestamp" to System.currentTimeMillis(), "sent" to false
)
```

## Тестирование логики без сети
Юнит-прогон с моками подтвердил полный цикл: поиск uid по username → send_each с
title/body/data/channel=chat/priority=high → SET delivered → UPDATE outbox sent=true.

## Read receipts (галки «прочитано») — read_relay.py

Схема «Вариант А»: клиент пишет receipt только в СВОЙ узел
`/chat-read-status/{chatId}/{readerUid}` = {ts, msgId} (правила RTDB это
разрешают без admin-прав). Собеседник читать чужой узел НЕ может — поэтому
релей копирует самый свежий receipt в служебный дочерний узел:

    /chat-read-status/{chatId}/{readerUid}/mirror = {ts, msgId, by}

Правила БД (app/database-rules.json Android-репозитория): `mirror` доступен на
чтение всем, кроме самого читателя, и записывается только релеем (admin).
Клиент-отправитель слушает `mirror` собеседника (DbPaths.chatReadMirror) и
красит две синие галки.

Запуск:
- web-режим (Render free + cron-job.org): `/flush` уже дёргает read-релей тем
  же ударом раз в минуту; отдельно есть `POST /flush_read_status` и диагностика
  `GET /debug_read_status`;
- worker-режим: подписка child_added/changed на `chat-read-status` — зеркало
  обновляется мгновенно, плюс фолбэк-поллинг раз в минуту.
