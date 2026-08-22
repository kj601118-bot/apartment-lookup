# -*- coding: utf-8 -*-
"""
주간 실거래가 업데이트 스크립트.
당월 + 직전 2개월 데이터를 재조회하여(국토부 실거래 신고는 계약 후 최대 30일 소요되므로
최근월은 매번 다시 확인해야 누락 없이 최신 반영됨) data/raw_transactions.csv 에 신규 건만 append 한다.
실행 후 "이번 주 신규 매칭 건"을 별도 diff 파일로도 남긴다.

주의: 이 스크립트는 최근 3개월만 재확인한다. 갱신을 오래 걸렀거나(예: 2주 이상 공백)
더 오래된 월의 지연신고 누락이 걱정되면 build_dataset.py(전체 재백필)를 대신 실행할 것.
"""
import csv
import datetime
import os

import config
from rtms_client import fetch_trades

BASE_DIR = os.path.dirname(__file__)
OUT_PATH = os.path.join(BASE_DIR, config.MASTER_CSV)

CSV_COLUMNS = [
    "지역", "umdNm", "aptNm", "buildYear", "addr", "excluUseAr", "floor",
    "dealYear", "dealMonth", "dealDay", "dealAmount_만원", "dealAmount_억",
]


def to_int_amount(s):
    return int(s.replace(",", "").strip())


def row_key(r):
    return (r["지역"], r["umdNm"], r["aptNm"], r["dealYear"], r["dealMonth"], r["dealDay"],
            r["floor"], r["excluUseAr"], str(r["dealAmount_만원"]))


def target_months(now, back=2):
    months = []
    y, m = now.year, now.month
    for _ in range(back + 1):
        months.append(f"{y:04d}{m:02d}")
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    return list(reversed(months))


def main():
    now = datetime.datetime.now()
    months = target_months(now)

    existing_keys = set()
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                existing_keys.add(row_key(r))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    write_header = not os.path.exists(OUT_PATH)
    f_out = open(OUT_PATH, "a", encoding="utf-8-sig", newline="")
    writer = csv.DictWriter(f_out, fieldnames=CSV_COLUMNS)
    if write_header:
        writer.writeheader()

    new_rows = []
    for lawd_cd, area_name in config.TARGET_LAWD.items():
        for ymd in months:
            try:
                rows = fetch_trades(lawd_cd, ymd)
            except Exception as e:
                print(f"[WARN] {area_name} {ymd} 조회 실패: {e}")
                continue
            for row in rows:
                try:
                    area_m2 = float(row["excluUseAr"])
                    amount = to_int_amount(row["dealAmount"])
                except ValueError:
                    continue
                if not (config.MIN_AREA_M2 <= area_m2 <= config.MAX_AREA_M2):
                    continue
                if not (config.MIN_PRICE_MAN <= amount <= config.MAX_PRICE_MAN):
                    continue

                out_row = {
                    "지역": area_name, "umdNm": row["umdNm"], "aptNm": row["aptNm"],
                    "buildYear": row["buildYear"],
                    "addr": (row["roadNm"] or row["jibun"]).strip(),
                    "excluUseAr": row["excluUseAr"], "floor": row["floor"],
                    "dealYear": row["dealYear"], "dealMonth": row["dealMonth"],
                    "dealDay": row["dealDay"], "dealAmount_만원": amount,
                    "dealAmount_억": round(amount / 10000, 2),
                }
                key_tuple = row_key(out_row)
                if key_tuple in existing_keys:
                    continue
                existing_keys.add(key_tuple)
                writer.writerow(out_row)
                new_rows.append(out_row)

    f_out.close()

    diff_path = os.path.join(BASE_DIR, "data", f"weekly_new_{now.strftime('%Y%m%d')}.csv")
    with open(diff_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in new_rows:
            w.writerow(r)

    print(f"신규 매칭 {len(new_rows)}건")
    print(f"diff 파일: {diff_path}")
    if new_rows:
        for r in sorted(new_rows, key=lambda r: -r["dealAmount_만원"])[:20]:
            print(f"  {r['지역']} {r['umdNm']} {r['aptNm']} {r['excluUseAr']}㎡ "
                  f"{r['dealAmount_억']}억 ({r['dealYear']}-{r['dealMonth']}-{r['dealDay']})")


if __name__ == "__main__":
    main()
