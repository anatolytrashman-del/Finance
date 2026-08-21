"""Общая директория локального хранилища приложения.

Все *_store.py модули (market_store, bir_store, rates_store, docs_store,
events_store, finmodel_store, ideas_store, db) держат свои файлы здесь —
раньше путь был скопирован в каждый модуль по отдельности.

Переопределяется переменной окружения APP_DATA_DIR — в контейнере (Fly.io)
туда монтируется persistent volume, чтобы данные переживали передеплой."""
import os
from pathlib import Path

APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR") or (Path.home() / ".trashman_family_office"))
