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
    if firebase_admin.get_app():  # уже инициализирован
        return

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        info = json.loads(sa_json)
        cred = credentials.Certificate(info)
    else:
        key_path = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json"
        )
        cred = credentials.Certificate(key_path)

    firebase_admin.initialize_app(cred, {
        "databaseURL": os.environ.get(
            "FIREBASE_DATABASE_URL",
            "https://kotlinmassage-default-rtdb.firebaseio.com",
        )
    })


def get_db():
    return db.reference()
