"""Инициализация Firebase Admin SDK.

Требует service account key:
  - локально: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/serviceAccountKey.json
  - Render/Fly.io: содержимое ключа в переменной FIREBASE_SERVICE_ACCOUNT (JSON-строка)
"""
import json
import os

import firebase_admin
from firebase_admin import credentials, db


def init_firebase() -> None:
    try:
        firebase_admin.get_app()  # уже инициализирован
        return
    except ValueError:
        pass  # default app ещё нет — идём инициализировать

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        info = json.loads(sa_json)
        cred = credentials.Certificate(info)
    else:
        key_path = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json"
        )
        cred = credentials.Certificate(key_path)

    # ВАЖНО: у проекта две разные БД в одном проекте:
    #   kotlinmassage-default-rtdb — НЕ существует (404), была захардкожена как дефолт,
    #     из-за чего весь релей читал пустоту и /flush давал processed:0;
    #   kotlinmessageres — живая база, куда пишет Android-клиент.
    database_url = os.environ.get("FIREBASE_DATABASE_URL")
    if not database_url:
        try:
            info = json.loads(os.environ.get("FIREBASE_SERVICE_ACCOUNT") or "{}")
        except Exception:
            info = {}
        project_id = info.get("project_id") or "kotlinmessageres"
        database_url = f"https://{project_id}-default-rtdb.firebaseio.com" \
            if "-default-rtdb" in project_id else f"https://{project_id}.firebaseio.com"
        # для kotlinmessageres реальное имя хоста именно такое:
        if project_id == "kotlinmessageres":
            database_url = "https://kotlinmessageres.firebaseio.com"
    firebase_admin.initialize_app(cred, {"databaseURL": database_url})


def get_db():
    return db.reference()
