"""Probe realt.by GraphQL API (/bff/graphql) — добивает недостающие детали:
тип "улица" в геопоиске и номера категорий коммерции по нашим адресам.

Лёгкий скрипт на requests (браузер не нужен). Сохраняет ответы в
realt_probe_debug/ и пакует в realt_probe_debug.zip — пришли его в чат.

Запуск:  python3 realt_probe.py
"""
import json
import zipfile
from collections import Counter
from pathlib import Path

import requests

ENDPOINT = "https://realt.by/bff/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://realt.by",
    "Referer": "https://realt.by/sale/flats/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "apollographql-client-name": "realt-web",
}

GEO_QUERY = "fragment MultiGeoData on MultiGeoReferenceAggData {\n  uuid\n  type\n  title\n  priority\n  stateRegionUuid\n  stateRegionName\n  stateDistrictUuid\n  stateDistrictName\n  townUuid\n  townName\n  townDistrictUuid\n  townDistrictName\n  townSubDistrictUuid\n  townSubDistrictName\n  location\n  townType\n  __typename\n}\n\nquery multiGeoReferenceAgg($data: GetMultiGeoReferenceAggInput!) {\n  multiGeoReferenceAgg(data: $data) {\n    body {\n      towns {\n        ...MultiGeoData\n        __typename\n      }\n      regions {\n        ...MultiGeoData\n        __typename\n      }\n      stateDistricts {\n        ...MultiGeoData\n        __typename\n      }\n      townDistricts {\n        ...MultiGeoData\n        __typename\n      }\n      townSubDistricts {\n        ...MultiGeoData\n        __typename\n      }\n      streets {\n        ...MultiGeoData\n        __typename\n      }\n      metros {\n        ...MultiGeoData\n        __typename\n      }\n      onlyTowns\n      __typename\n    }\n    ...StatusAndErrors\n    __typename\n  }\n}\n\nfragment StatusAndErrors on INullResponse {\n  success\n  errors {\n    code\n    title\n    message\n    field\n    __typename\n  }\n  __typename\n}"
SEARCH_QUERY = "query searchObjectsV2($data: GetObjectsByAddressInputV2!) {\n  searchObjectsV2(data: $data) {\n    ...StatusAndErrors\n    body {\n      pagination {\n        page\n        pageSize\n        totalCount\n        __typename\n      }\n      results {\n        companyName\n        companyUuid\n        uuid\n        unid\n        code\n        category\n        customSorting\n        raiseDate\n        createdAt\n        updatedAt\n        stateRegionUuid\n        stateRegionName\n        stateDistrictUuid\n        stateDistrictName\n        townUuid\n        townName\n        townCat\n        townType\n        townDistrictUuid\n        townSubDistrictUuid\n        streetUuid\n        streetName\n        houseNumber\n        buildingNumber\n        address\n        metroLineUuid\n        metroStationUuid\n        metroTime\n        metroTimeType\n        townDistance\n        location\n        priceCurrency\n        price\n        priceMin\n        priceMax\n        pricePerM2\n        pricePerPerson\n        pricePerM2Max\n        priceChangeDirection\n        priceChangeDate\n        leasePeriod\n        termOfLease\n        termsOfSale\n        prepayment\n        housingRent\n        buildingYear\n        storeys\n        storey\n        wallMaterial\n        ceilingHeight\n        repairState\n        toilet\n        sewerage\n        furniture\n        appliances\n        planing\n        equipment\n        floorType\n        levels\n        heating\n        gas\n        electricity\n        water\n        housePlotArea\n        roofMaterial\n        completionPercent\n        overhaulYear\n        houseType\n        balconyType\n        levelType\n        parkingPlace\n        daylight\n        legalAddress\n        commercialObjectType\n        maxCapacity\n        ownType\n        extraInfo\n        rooms\n        commercialRoomsMax\n        commercialRoomsMin\n        separateRooms\n        areaTotal\n        areaLiving\n        areaKitchen\n        areaLand\n        title\n        headline\n        description\n        images\n        hasImages\n        hasVideo\n        has3dTour\n        isFavorite\n        seller\n        contactPhones\n        contactName\n        contactEmail\n        agencyUuid\n        agencyName\n        metroStationName\n        metroLineId\n        paymentStatus\n        comments\n        objectCategory\n        placeTypes\n        availableYear\n        benefitCredit\n        owner\n        privatization\n        directionName\n        officeNumber\n        directionUuid\n        nds\n        isFirstStorey\n        isLastStorey\n        allSeparate\n        numberOfBeds\n        objectType\n        extraObjectTypes\n        areaMin\n        areaMax\n        isNewBuild\n        isAuction\n        newBuildComplex\n        realEstateDevUuid\n        separateEnter\n        class\n        place\n        infrastructure\n        layout\n        nearLake\n        userUuid\n        availableQuarter\n        availableAlready\n        availableText\n        isSellingCompleted\n        communicationMethod\n        interactiveCatalogToken\n        interactiveCatalogBaseToken\n        isObjectInRealtyDeal\n        __typename\n      }\n      sort {\n        by\n        order\n        __typename\n      }\n      rates {\n        from\n        to\n        rate\n        __typename\n      }\n      extraFields {\n        minPriceAggregation\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment StatusAndErrors on INullResponse {\n  success\n  errors {\n    code\n    title\n    message\n    field\n    __typename\n  }\n  __typename\n}"

ADDRESSES = [("Михаила Савицкого", "24"), ("Жореса Алфёрова", "22")]
TYPE_VARIANTS = [[5], [7], [4], [2, 3, 5], [3, 4, 5, 6, 7]]

OUT = Path(__file__).parent / "realt_probe_debug"
ZIP_PATH = Path(__file__).parent / "realt_probe_debug.zip"


def gql(op, query, variables):
    payload = [{"operationName": op, "variables": variables, "query": query}]
    r = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data[0] if isinstance(data, list) else data


def main():
    OUT.mkdir(exist_ok=True)
    summary = []
    for street, house in ADDRESSES:
        found_uuid = None
        for types in TYPE_VARIANTS:
            try:
                resp = gql("multiGeoReferenceAgg", GEO_QUERY,
                           {"data": {"where": {"title": street, "types": types}, "pageSize": 10}})
            except Exception as exc:
                summary.append(f"geo '{street}' types={types} -> ERROR: {exc}")
                continue
            (OUT / f"geo_{street.split()[-1]}_{'_'.join(map(str, types))}.json").write_text(
                json.dumps(resp, ensure_ascii=False, indent=1), encoding="utf-8")
            streets = (((resp.get("data") or {}).get("multiGeoReferenceAgg") or {}).get("body") or {}).get("streets")
            if streets:
                summary.append(f"geo '{street}' types={types}: " +
                               str([f"{s.get('title')}(t{s.get('type')})" for s in streets[:5]]))
                if not found_uuid:
                    key = street.split()[-1].lower()
                    match = next((s for s in streets if key in (s.get("title") or "").lower()), streets[0])
                    found_uuid = match.get("uuid")
            else:
                summary.append(f"geo '{street}' types={types}: streets=none")

        if found_uuid:
            try:
                resp = gql("searchObjectsV2", SEARCH_QUERY,
                           {"data": {"where": {"addressV2": [{"streetUuid": found_uuid}]}}})
                (OUT / f"objects_{street.split()[-1]}.json").write_text(
                    json.dumps(resp, ensure_ascii=False, indent=1), encoding="utf-8")
                b = (((resp.get("data") or {}).get("searchObjectsV2") or {}).get("body") or {})
                results = b.get("results") or []
                total = (b.get("pagination") or {}).get("totalCount")
                cats = Counter((o.get("category"), o.get("objectType")) for o in results)
                houses = Counter(str(o.get("houseNumber")) for o in results)
                summary.append(f"OBJECTS '{street}' uuid={found_uuid} total={total} got={len(results)} "
                               f"cats={dict(cats)} houses={dict(houses)}")
            except Exception as exc:
                summary.append(f"objects '{street}' -> ERROR: {exc}")
        else:
            summary.append(f"!! streetUuid not found for '{street}'")

    (OUT / "index.txt").write_text("\n".join(summary), encoding="utf-8")
    print("\n".join(summary))
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT.iterdir()):
            zf.write(f, f.name)
    print(f"\nGotovo! Prishli fajl: {ZIP_PATH}")


if __name__ == "__main__":
    main()
