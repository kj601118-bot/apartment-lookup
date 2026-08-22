# -*- coding: utf-8 -*-
"""
2026년 1월 ~ 현재월까지의 아파트 매매 실거래가를 전량 수집하여
조건(전용면적 58~60.5㎡, 거래금액 11~15억)에 맞는 건만 필터링해
data/raw_transactions.csv 로 저장한다. (전체 재백필 겸 최신화용 — 매번 전체 기간을 다시 훑어
RTMS의 지연신고(최대 30일)로 뒤늦게 잡히는 과거월 거래도 빠짐없이 반영한다)
"""
import csv
import datetime
import os
import sys
import time

import config
from rtms_client import fetch_trades

OUT_PATH = os.path.join(os.path.dirname(__file__), config.MASTER_CSV)

CSV_COLUMNS = [
    "지역", "umdNm", "aptNm", "buildYear", "addr", "excluUseAr", "floor",
    "dealYear", "dealMonth", "dealDay", "dealAmount_만원", "dealAmount_억",
]


def month_range(start_year, start_month, end_year, end_month):
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        yield f"{y:04d}{m:02d}"
        m += 1
        if m > 12:
            m = 1
            y += 1


def to_int_amount(s):
    return int(s.replace(",", "").strip())


def row_key(r):
    return (r["지역"], r["umdNm"], r["aptNm"], r["dealYear"], r["dealMonth"], r["dealDay"],
            r["floor"], r["excluUseAr"], str(r["dealAmount_만원"]))


def main():
    now = datetime.datetime.now()
    months = list(month_range(2026, 1, now.year, now.month))

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

    total_fetched = 0
    total_matched = 0
    total_new = 0

    for lawd_cd, area_name in config.TARGET_LAWD.items():
        for ymd in months:
            try:
                rows = fetch_trades(lawd_cd, ymd)
            except Exception as e:
                print(f"[WARN] {area_name} {ymd} 조회 실패: {e}", file=sys.stderr)
                continue
            total_fetched += len(rows)
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
                total_matched += 1

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
                total_new += 1
                writer.writerow(out_row)
            time.sleep(0.15)  # API 과호출 방지
        print(f"[OK] {area_name} 완료 (누적 매칭 {total_matched}건)")

    f_out.close()
    print(f"\n총 조회 {total_fetched}건 / 조건 매칭 {total_matched}건 / 신규 저장 {total_new}건")
    print(f"저장 위치: {OUT_PATH}")


if __name__ == "__main__":
    main()
