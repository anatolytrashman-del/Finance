"""Общая директория локального хранилища приложения.

Все *_store.py модули (market_store, bir_store, rates_store, docs_store,
events_store, finmodel_store, ideas_store) держат свои файлы здесь — раньше
путь был скопирован в каждый модуль по отдельности."""
from pathlib import Path

APP_DATA_DIR = Path.home() / ".trashman_family_office"
