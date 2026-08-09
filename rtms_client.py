# -*- coding: utf-8 -*-
"""
국토교통부 아파트매매 실거래가 상세자료 API 클라이언트
API 문서: RTMSDataSvcAptTradeDev (공공데이터포털 1613000)
"""
import os
import time
import xml.etree.ElementTree as ET

import requests

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


def load_env(path=ENV_PATH):
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip()
    return env


ENV = load_env()
ENDPOINT = ENV["RTMS_DETAIL_ENDPOINT"] + "/getRTMSDataSvcAptTradeDev"
SERVICE_KEY = ENV["RTMS_DETAIL_SERVICE_KEY"]

FIELDS = [
    "sggCd", "umdNm", "aptNm", "aptSeq", "jibun", "roadNm",
    "buildYear", "excluUseAr", "floor",
    "dealYear", "dealMonth", "dealDay", "dealAmount",
    "dealingGbn", "cdealType", "cdealDay",
]


def _text(item, tag):
    el = item.find(tag)
    return el.text.strip() if el is not None and el.text else ""


def fetch_trades(lawd_cd, deal_ymd, num_of_rows=1000, max_retries=3):
    """지정 시군구(lawd_cd) / 계약년월(YYYYMM)의 아파트 매매 실거래 목록을 반환한다."""
    params = {
        "serviceKey": SERVICE_KEY,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "numOfRows": num_of_rows,
        "pageNo": 1,
    }
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(ENDPOINT, params=params, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            result_code = root.findtext("./header/resultCode")
            if result_code != "000":
                result_msg = root.findtext("./header/resultMsg")
                raise RuntimeError(f"API error {result_code}: {result_msg}")

            rows = []
            for item in root.findall("./body/items/item"):
                row = {f: _text(item, f) for f in FIELDS}
                rows.append(row)
            return rows
        except (requests.RequestException, ET.ParseError, RuntimeError) as e:
            if attempt == max_retries:
                raise
            time.sleep(1.5 * attempt)
    return []
