# -*- coding: utf-8 -*-
"""
transactions.csv 의 단지 목록을 OpenStreetMap Nominatim으로 지오코딩해
data/geocache.csv 에 위도/경도를 캐싱한다. (무료, API 키 불필요, 1건/1.1초 제한 준수)
이미 캐시된 단지는 재조회하지 않으므로 여러 번 실행해도 안전하다.
"""
import csv
import os
import time

import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

TX_PATH = "data/raw_transactions.csv"
CACHE_PATH = "data/geocache.csv"

df = pd.read_csv(TX_PATH, encoding="utf-8-sig")
complexes = (
    df.groupby(["지역", "umdNm", "aptNm"], as_index=False)
    .agg(buildYear=("buildYear", "first"), addr=("addr", "first"))
)
print(f"전체 단지 {len(complexes)}개")

cached = {}
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cached[(r["지역"], r["umdNm"], r["aptNm"])] = r

geolocator = Nominatim(user_agent="apartment-purchase-lookup-app-personal-use")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1, max_retries=2, error_wait_seconds=3.0)

fieldnames = ["지역", "umdNm", "aptNm", "buildYear", "addr_display", "lat", "lon", "match_query"]
out_rows = list(cached.values())
new_count = 0

for _, row in complexes.iterrows():
    key = (row["지역"], row["umdNm"], row["aptNm"])
    if key in cached:
        continue

    region, dong, name = row["지역"], row["umdNm"], row["aptNm"]
    addr_display = str(row["addr"]).strip() if pd.notna(row["addr"]) else ""

    candidates = []
    if addr_display:
        candidates.append(f"대한민국 {region} {dong} {addr_display}")
    candidates.append(f"대한민국 {region} {dong}")

    lat = lon = ""
    matched_query = ""
    for q in candidates:
        try:
            loc = geocode(q, country_codes="kr", exactly_one=True, timeout=10)
        except Exception as e:
            print(f"  [WARN] '{q}' 조회 실패: {e}")
            loc = None
        if loc:
            lat, lon, matched_query = loc.latitude, loc.longitude, q
            break

    out_rows.append({
        "지역": region, "umdNm": dong, "aptNm": name, "buildYear": row["buildYear"],
        "addr_display": addr_display, "lat": lat, "lon": lon, "match_query": matched_query,
    })
    new_count += 1
    status = "OK" if lat else "실패"
    print(f"[{new_count}] {region} {dong} {name} -> {status} ({matched_query})")

with open(CACHE_PATH, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in out_rows:
        w.writerow(r)

ok = sum(1 for r in out_rows if r.get("lat"))
print(f"\n완료: 총 {len(out_rows)}개 중 좌표 확보 {ok}개, 신규 조회 {new_count}개")
print(f"저장 위치: {CACHE_PATH}")
