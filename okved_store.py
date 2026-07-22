"""Локальный справочник кодов ОКВЭД — чтобы на странице «Юрлица» выбирать
вид деятельности из списка, а не вбивать описание руками каждый раз.

При первом запуске сеется список кодов из скриншота пользователя (его ИП) —
дальше список можно пополнять прямо в приложении, без правок кода."""
import json

from local_store import APP_DATA_DIR

OKVED_PATH = APP_DATA_DIR / "okved_reference.json"

DEFAULT_OKVED = [
    {"code": "73.11", "description": "Деятельность рекламных агентств"},
    {"code": "58.29", "description": "Издание прочих программных продуктов"},
    {"code": "62.09", "description": "Деятельность, связанная с использованием вычислительной техники и информационных технологий, прочая"},
    {"code": "63.11", "description": "Деятельность по обработке данных, предоставление услуг по размещению информации и связанная с этим деятельность"},
    {"code": "63.12", "description": "Деятельность web-порталов"},
    {"code": "63.91", "description": "Деятельность информационных агентств"},
    {"code": "68.10", "description": "Покупка и продажа собственного недвижимого имущества"},
    {"code": "68.20", "description": "Аренда и управление собственным или арендованным недвижимым имуществом"},
    {"code": "73.12", "description": "Представление в средствах массовой информации"},
]


def load_okved():
    if OKVED_PATH.exists():
        try:
            data = json.loads(OKVED_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except Exception:  # noqa: BLE001
            pass
    # первый запуск — справочника ещё нет, сеем стартовый список
    save_okved(DEFAULT_OKVED)
    return list(DEFAULT_OKVED)


def save_okved(codes):
    OKVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    OKVED_PATH.write_text(json.dumps(codes, ensure_ascii=False, indent=2), encoding="utf-8")
