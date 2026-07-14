# ID гугл-таблицы (из ссылки docs.google.com/spreadsheets/d/<ID>/edit)
# Таблица должна быть открыта на чтение: "Все, у кого есть ссылка" -> Читатель
GOOGLE_SHEET_ID = "1RRkaYwhhAnX5c59ogz9h6VXEO1LV6QQDJKkIfvKnbc4"

# Ключ Yandex Maps JavaScript API (developer.tech.yandex.ru) — только для JavaScript API
YANDEX_MAPS_API_KEY = "a7182a37-1597-4b71-9bc0-aaa154b92d13"

# Адреса, по которым мониторим объявления на странице «Рынок».
# house_tag    — точный геотег дома из данных kufar (фильтрует строго по дому)
# realt_street — название улицы для гео-поиска realt.by; house — номер дома
MONITORED_ADDRESSES = [
    {
        "label": "Михаила Савицкого, 24",
        "query": "Михаила Савицкого 24",
        "house_tag": "street-ulica_mihaila_savickogo~house-24",
        "realt_street": "Михаила Савицкого",
        "house": "24",
    },
    {
        "label": "Жореса Алфёрова, 22",
        "query": "Жореса Алфёрова 22",
        "house_tag": "street-ulica_zhoresa_alfyorova~house-22",
        "realt_street": "Жореса Алфёрова",
        "house": "22",
    },
]
