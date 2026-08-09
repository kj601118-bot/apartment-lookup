# -*- coding: utf-8 -*-
"""webdata.json(원본 거래 백업)에서 data/raw_transactions.csv 를 복구한다."""
import csv
import json

with open("data/webdata.json", encoding="utf-8") as f:
    raw = json.load(f)

complexes = raw["complexes"]  # [region, dong, name, buildYear, addr]
fieldnames = ["지역", "umdNm", "aptNm", "buildYear", "addr", "excluUseAr", "floor",
              "dealYear", "dealMonth", "dealDay", "dealAmount_만원", "dealAmount_억"]

with open("data/raw_transactions.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for cid, y, m, d, amount, floor, area in raw["transactions"]:
        region, dong, name, buildYear, addr = complexes[cid]
        w.writerow({
            "지역": region, "umdNm": dong, "aptNm": name, "buildYear": buildYear, "addr": addr,
            "excluUseAr": area, "floor": floor,
            "dealYear": y, "dealMonth": m, "dealDay": d,
            "dealAmount_만원": amount, "dealAmount_억": round(amount / 10000, 2),
        })

print(f"복구 완료: {len(raw['transactions'])}건")
