"""Локальное хранилище цен застройщика (bir.by).

Файлы лежат в домашней директории — переживают обновление кода."""
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / ".trashman_family_office"
LISTINGS_PATH = BASE_DIR / "bir_listings.json"
SEEN_PATH = BASE_DIR / "bir_seen.json"
ARCHIVE_PATH = BASE_DIR / "bir_archive.json"


def load_listings():
    """Возвращает dict {'fetched_at': str, 'listings': [...], 'warnings': [...]} или None."""
    if LISTINGS_PATH.exists():
        try:
            return json.loads(LISTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


def save_listings(listings, warnings):
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "listings": listings,
        "warnings": warnings,
    }
    LISTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload


# --- Отслеживание «новых» юнитов и архив ушедших с сайта -------------------

def load_seen():
    """{id: дата_первого_появления_iso}. Нужно, чтобы отличать новые юниты
    и считать срок экспозиции ушедших в архив."""
    if SEEN_PATH.exists():
        try:
            data = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_seen(seen):
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False, indent=1), encoding="utf-8")


def load_archive():
    if ARCHIVE_PATH.exists():
        try:
            data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:  # noqa: BLE001
            return []
    return []


def append_archive(records):
    """Добавляет записи о юнитах, пропавших из последней выдачи (проданы/сняты)."""
    if not records:
        return load_archive()
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    archive = load_archive()
    archive.extend(records)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=1), encoding="utf-8")
    return archive
