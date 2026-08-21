# -*- coding: utf-8 -*-
"""
공동주택 단지 목록제공 서비스(AptListService3)로 TARGET_LAWD 각 시군구의
전체 단지(kaptCode, 단지명, 동) 목록을 수집해 data/kaptlist_cache.csv 로 저장한다.
"""
import csv
import time

import requests

import config
from rtms_client import load_env

ENV = load_env()
ENDPOINT = ENV["APT_LIST_ENDPOINT"] + "/getSigunguAptList3"
SERVICE_KEY = ENV["APT_LIST_SERVICE_KEY"]


def fetch_district(sigungu_cd, num_of_rows=1000, max_retries=3):
    params = {
        "serviceKey": SERVICE_KEY,
        "sigunguCode": sigungu_cd,
        "numOfRows": num_of_rows,
        "pageNo": 1,
    }
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(ENDPOINT, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            body = data["response"]["body"]
            total = body.get("totalCount", 0)
            items = body.get("items") or []
            if total > num_of_rows:
                print(f"  [WARN] {sigungu_cd}: totalCount({total}) > numOfRows({num_of_rows}), 일부 누락 가능")
            return items
        except Exception as e:
            if attempt == max_retries:
                raise
            time.sleep(1.5 * attempt)
    return []


def main():
    rows = []
    for sigungu_cd, area_name in config.TARGET_LAWD.items():
        items = fetch_district(sigungu_cd)
        for it in items:
            rows.append({
                "지역": area_name,
                "umdNm": it.get("as3") or "",
                "kaptName": it.get("kaptName") or "",
                "kaptCode": it.get("kaptCode") or "",
                "bjdCode": it.get("bjdCode") or "",
            })
        print(f"[OK] {area_name} ({sigungu_cd}): {len(items)}개 단지")
        time.sleep(0.15)

    with open("data/kaptlist_cache.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["지역", "umdNm", "kaptName", "kaptCode", "bjdCode"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"\n총 {len(rows)}개 단지 저장: data/kaptlist_cache.csv")


if __name__ == "__main__":
    main()
