# -*- coding: utf-8 -*-
"""
raw_transactions.csv 의 단지들을 kaptlist_cache.csv(단지명->kaptCode)와 매칭한 뒤
공동주택 기본 정보제공 서비스(AptBasisInfoServiceV4)로 세대수·시공사 등을 조회해
data/aptinfo_cache.csv 로 저장한다.
"""
import csv
import re
import time

import pandas as pd
import requests

from rtms_client import load_env

ENV = load_env()
ENDPOINT = ENV["APT_BASIS_ENDPOINT"] + "/getAphusBassInfoV4"
SERVICE_KEY = ENV["APT_BASIS_SERVICE_KEY"]


SUFFIXES = ("아파트", "apt", "APT")


def normalize(name):
    name = re.sub(r"[\s()·,\-]", "", str(name))
    for suf in SUFFIXES:
        if name.endswith(suf):
            name = name[: -len(suf)]
            break
    return name.lower()


def dong_prefixes(dong):
    """'자양동' -> ['자양동', '자양'] 처럼 동명 접두어 후보를 만든다 (K-apt가 동명을 단지명 앞에 붙이는 경우 대응)"""
    core = re.sub(r"\d*(동|가|리)$", "", str(dong))
    prefixes = []
    if dong:
        prefixes.append(str(dong))
    if core and core != dong:
        prefixes.append(core)
    return prefixes


def strip_dong_prefix(name, dong):
    for p in dong_prefixes(dong):
        p_norm = normalize(p)
        if p_norm and name.startswith(p_norm) and len(name) > len(p_norm):
            return name[len(p_norm):]
    return name


def load_kapt_list():
    df = pd.read_csv("data/kaptlist_cache.csv", encoding="utf-8-sig")
    buckets = {}
    for _, r in df.iterrows():
        key = (r["지역"], r["umdNm"])
        buckets.setdefault(key, []).append((r["kaptName"], r["kaptCode"]))
    return buckets


def match_kapt_code(apt_name, dong, candidates):
    norm_target = normalize(apt_name)
    if not norm_target:
        return None, "no_name"

    exact = [c for c in candidates if normalize(c[0]) == norm_target]
    if len(exact) == 1:
        return exact[0][1], "exact"
    if len(exact) > 1:
        return exact[0][1], "exact_ambiguous"

    contains = [c for c in candidates if norm_target in normalize(c[0]) or normalize(c[0]) in norm_target]
    if len(contains) == 1:
        return contains[0][1], "contains"
    if len(contains) > 1:
        contains.sort(key=lambda c: abs(len(normalize(c[0])) - len(norm_target)))
        return contains[0][1], "contains_ambiguous"

    # K-apt가 단지명 앞에 동명을 붙이는 흔한 패턴 대응 (예: RTMS "자양삼성" vs K-apt "자양동삼성아파트")
    target_dedong = strip_dong_prefix(norm_target, dong)
    dedong = [
        c for c in candidates
        if strip_dong_prefix(normalize(c[0]), dong) == target_dedong
        or target_dedong in strip_dong_prefix(normalize(c[0]), dong)
        or strip_dong_prefix(normalize(c[0]), dong) in target_dedong
    ]
    if len(dedong) == 1:
        return dedong[0][1], "dedong"
    if len(dedong) > 1:
        dedong.sort(key=lambda c: abs(len(strip_dong_prefix(normalize(c[0]), dong)) - len(target_dedong)))
        return dedong[0][1], "dedong_ambiguous"

    return None, "no_match"


def fetch_basis_info(kapt_code, max_retries=3):
    params = {"serviceKey": SERVICE_KEY, "kaptCode": kapt_code}
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(ENDPOINT, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            item = data["response"]["body"].get("item")
            return item or {}
        except Exception:
            if attempt == max_retries:
                return {}
            time.sleep(1.0 * attempt)
    return {}


def main():
    tx = pd.read_csv("data/raw_transactions.csv", encoding="utf-8-sig")
    complexes = tx[["지역", "umdNm", "aptNm"]].drop_duplicates().reset_index(drop=True)
    print(f"매칭 대상 단지: {len(complexes)}개")

    buckets = load_kapt_list()

    match_stats = {}
    rows = []
    basis_cache = {}

    for i, r in complexes.iterrows():
        region, dong, name = r["지역"], r["umdNm"], r["aptNm"]
        candidates = buckets.get((region, dong), [])
        kapt_code, match_type = match_kapt_code(name, dong, candidates)
        match_stats[match_type] = match_stats.get(match_type, 0) + 1

        households = None
        builder = None
        dong_cnt = None
        used_date = None
        if kapt_code:
            if kapt_code not in basis_cache:
                basis_cache[kapt_code] = fetch_basis_info(kapt_code)
                time.sleep(0.12)
            info = basis_cache[kapt_code]
            households = info.get("kaptdaCnt")
            builder = info.get("kaptBcompany")
            dong_cnt = info.get("kaptDongCnt")
            used_date = info.get("kaptUsedate")

        rows.append({
            "지역": region, "umdNm": dong, "aptNm": name,
            "kaptCode": kapt_code or "", "matchType": match_type,
            "세대수": households or "", "시공사": builder or "",
            "동수": dong_cnt or "", "사용승인일": used_date or "",
        })
        if (i + 1) % 50 == 0:
            print(f"  진행 {i + 1}/{len(complexes)}")

    with open("data/aptinfo_cache.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["지역", "umdNm", "aptNm", "kaptCode", "matchType",
                                            "세대수", "시공사", "동수", "사용승인일"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    matched = sum(1 for r in rows if r["세대수"])
    print(f"\n매칭 통계: {match_stats}")
    print(f"세대수 확보: {matched}/{len(rows)}개")
    print("저장 위치: data/aptinfo_cache.csv")


if __name__ == "__main__":
    main()
