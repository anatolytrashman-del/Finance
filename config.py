# ID гугл-таблицы (из ссылки docs.google.com/spreadsheets/d/<ID>/edit)
# Таблица должна быть открыта на чтение: "Все, у кого есть ссылка" -> Читатель
GOOGLE_SHEET_ID = "1RRkaYwhhAnX5c59ogz9h6VXEO1LV6QQDJKkIfvKnbc4"

# Ключ Yandex Maps JavaScript API (developer.tech.yandex.ru) — только для JavaScript API
YANDEX_MAPS_API_KEY = "a7182a37-1597-4b71-9bc0-aaa154b92d13"

# Адреса, по которым мониторим объявления на странице «Анализ рынка» —
# сгруппированы по кварталам застройки (на странице показываются одним блоком).
#
# house_tag    — геотег дома из данных kufar (транслитерация Yandex/kufar).
#                Для «Михаила Савицкого» подтверждён живыми данными (дома 24/25/27
#                на одной улице — меняется только номер). Для «Игоря Лученка» и
#                «Братская» — НЕ подтверждён (транслитерацию не проверить без
#                живого доступа к kufar), поэтому это лишь вспомогательная догадка:
#                если тег не совпадёт, сработает резервное сопоставление по тексту
#                объявления (см. market_kufar._text_match) — ни один дом не
#                останется без результатов только из-за неверной транслитерации.
# realt_street — название улицы для гео-поиска realt.by (последнее слово в строке
#                используется как ключ поиска — поэтому «Братская», без «улица»)
# house        — номер дома
MONITORED_QUARTALS = [
    {
        "name": "16 квартал",
        "addresses": [
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
        ],
    },
    {
        "name": "11 квартал",
        "addresses": [
            {
                "label": "Михаила Савицкого, 25",
                "query": "Михаила Савицкого 25",
                "house_tag": "street-ulica_mihaila_savickogo~house-25",
                "realt_street": "Михаила Савицкого",
                "house": "25",
            },
            {
                "label": "Игоря Лученка, 20",
                "query": "Игоря Лученка 20",
                "house_tag": "street-ulica_igorya_luchenka~house-20",  # непроверено
                "realt_street": "Игоря Лученка",
                "house": "20",
            },
            {
                "label": "Игоря Лученка, 18",
                "query": "Игоря Лученка 18",
                "house_tag": "street-ulica_igorya_luchenka~house-18",  # непроверено
                "realt_street": "Игоря Лученка",
                "house": "18",
            },
            {
                "label": "Игоря Лученка, 22",
                "query": "Игоря Лученка 22",
                "house_tag": "street-ulica_igorya_luchenka~house-22",  # непроверено
                "realt_street": "Игоря Лученка",
                "house": "22",
            },
            {
                "label": "Братская улица, 24",
                "query": "Братская 24",
                "house_tag": "street-ulica_bratskaya~house-24",  # непроверено
                "realt_street": "Братская",
                "house": "24",
            },
            {
                "label": "Михаила Савицкого, 27",
                "query": "Михаила Савицкого 27",
                "house_tag": "street-ulica_mihaila_savickogo~house-27",
                "realt_street": "Михаила Савицкого",
                "house": "27",
            },
        ],
    },
]

# Плоский список адресов — источники (kufar/realt) как и раньше собирают
# объявления по каждому адресу отдельно; группировка по кварталам нужна
# только для отображения на странице.
MONITORED_ADDRESSES = [addr for q in MONITORED_QUARTALS for addr in q["addresses"]]

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
REALESTATE_MARKET_COLUMN = "Примерная рыночная стоимость в $"  # для модели «покупка + аренда»
REALESTATE_TYPE_COLUMN = "Тип"
REALESTATE_LOCATION_COLUMN = "Локация"
