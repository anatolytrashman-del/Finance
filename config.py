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

# --- Связка «Сделки» ↔ объекты для финмодели продажи ---------------------
# Финмодель продажи умеет подтягивать платежи по объекту из листа «Сделки».
# Чтобы связать платёж с объектом точно (без угадывания по тексту), добавь в
# «Сделки» столбец-ярлык объекта (DEALS_OBJECT_COLUMN) и заполни его коротким
# именем, совпадающим с таким же столбцом в «Real Estate» (REALESTATE_OBJECT_COLUMN).
# Если столбца-ярлыка нет — код ищет имя объекта по вхождению в DEALS_PURPOSE_COLUMN.
DEALS_OBJECT_COLUMN = "Объект"            # точный ярлык объекта в «Сделки»
DEALS_PURPOSE_COLUMN = "Назначение"       # запасной текстовый столбец для поиска
DEALS_TYPE_COLUMN = "Тип сделки"
DEALS_DATE_COLUMN = "Дата"
DEALS_AMOUNT_COLUMN = "Сумма"
DEALS_PURCHASE_VALUE = "Покупка"          # значение «Тип сделки» = взнос по объекту

REALESTATE_OBJECT_COLUMN = "Объект"       # тот же ярлык в «Real Estate» (необязательно)
REALESTATE_PURCHASE_COLUMN = "Сумма покупки в $"
REALESTATE_TYPE_COLUMN = "Тип"
REALESTATE_LOCATION_COLUMN = "Локация"
