# -*- coding: utf-8 -*-
"""transactions.csv -> 웹 조회 페이지용 압축 JSON(complexes, transactions) 생성"""
import csv
import json

with open("data/raw_transactions.csv", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

# 세대수: matchType이 exact/contains(비모호)인 경우만 신뢰
households = {}
try:
    with open("data/aptinfo_cache.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["matchType"] in ("exact", "contains", "dedong") and r["세대수"]:
                households[(r["지역"], r["umdNm"], r["aptNm"])] = int(float(r["세대수"]))
except FileNotFoundError:
    pass

complex_index = {}  # (지역, 동, 아파트명) -> id
complexes = []      # [region, dong, name, buildYear, addr, households|null]
transactions = []   # [complexId, year, month, day, amount(만원), floor, area]

for r in rows:
    key = (r["지역"], r["umdNm"], r["aptNm"])
    if key not in complex_index:
        addr = r["addr"].strip()
        hh = households.get(key)
        complex_index[key] = len(complexes)
        complexes.append([r["지역"], r["umdNm"], r["aptNm"], r["buildYear"], addr, hh])
    cid = complex_index[key]
    try:
        amount = int(r["dealAmount_만원"])
        year = int(r["dealYear"])
        month = int(r["dealMonth"])
        day = int(r["dealDay"])
        floor = int(r["floor"])
        area = float(r["excluUseAr"])
    except ValueError:
        continue
    transactions.append([cid, year, month, day, amount, floor, area])

payload = {"complexes": complexes, "transactions": transactions}
out = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

with open("data/webdata.json", "w", encoding="utf-8") as f:
    f.write(out)

print(f"단지 {len(complexes)}개, 거래 {len(transactions)}건")
print(f"JSON 크기: {len(out.encode('utf-8'))/1024:.1f} KB")
