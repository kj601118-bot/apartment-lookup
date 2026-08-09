# -*- coding: utf-8 -*-
"""서울·경기 아파트 실거래가 조회 — Streamlit 공개 웹앱"""
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

SERIES_COLORS = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#008300", "#4a3aa7", "#e34948",
]

st.set_page_config(page_title="서울·경기 아파트 실거래가 조회", page_icon="🏢", layout="wide")


@st.cache_data
def load_transactions():
    df = pd.read_csv("data/raw_transactions.csv", encoding="utf-8-sig")
    df["umdNm"] = df["umdNm"].astype(str)
    df["aptNm"] = df["aptNm"].astype(str)
    df["ym"] = df["dealYear"] * 100 + df["dealMonth"]
    df["억"] = df["dealAmount_만원"] / 10000
    return df


@st.cache_data
def load_geo():
    try:
        return pd.read_csv("data/geocache.csv", encoding="utf-8-sig")
    except FileNotFoundError:
        return pd.DataFrame(columns=["지역", "umdNm", "aptNm", "lat", "lon", "addr_display"])


def ym_add(ym, delta):
    y, m = divmod(ym, 100)
    m += delta
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y * 100 + m


df = load_transactions()
geo = load_geo()

max_ym = int(df["ym"].max())
recent_window = {ym_add(max_ym, -2), ym_add(max_ym, -1), max_ym}
recent_label = f"{ym_add(max_ym, -2) // 100}.{ym_add(max_ym, -2) % 100:02d} ~ {max_ym // 100}.{max_ym % 100:02d}"

st.title("서울·경기 아파트 실거래가 조회")
st.caption(
    "국토교통부 실거래가공개시스템 API 기반 · 전용 58~60.5㎡ · 2026년 실측 거래 데이터 "
    f"· 최근 3개월 기준월: {recent_label}"
)

# ---------------- Filters ----------------
c1, c2, c3 = st.columns(3)
regions = sorted(df["지역"].unique())
sel_regions = c1.multiselect("지역", regions)

pool = df[df["지역"].isin(sel_regions)] if sel_regions else df
dongs = sorted(pool["umdNm"].unique())
sel_dongs = c2.multiselect("동", dongs)

pool2 = pool[pool["umdNm"].isin(sel_dongs)] if sel_dongs else pool
apts = sorted(pool2["aptNm"].unique())
sel_apts = c3.multiselect("아파트명", apts)

filtered = df
if sel_regions:
    filtered = filtered[filtered["지역"].isin(sel_regions)]
if sel_dongs:
    filtered = filtered[filtered["umdNm"].isin(sel_dongs)]
if sel_apts:
    filtered = filtered[filtered["aptNm"].isin(sel_apts)]

# ---------------- Complex-level summary ----------------
rows = []
for key, g in filtered.groupby(["지역", "umdNm", "aptNm", "buildYear"]):
    recent = g[g["ym"].isin(recent_window)]
    last_row = g.sort_values(["dealYear", "dealMonth", "dealDay"]).iloc[-1]
    rows.append({
        "선택": False,
        "지역": key[0], "동": key[1], "아파트명": key[2], "준공년도": int(key[3]),
        "최근3개월평균(억)": round(recent["억"].mean(), 2) if len(recent) else None,
        "최근3개월건수": len(recent),
        "전체거래건수": len(g),
        "최근거래일": f"{int(last_row.dealYear)}-{int(last_row.dealMonth):02d}-{int(last_row.dealDay):02d}",
    })
summary = pd.DataFrame(rows).sort_values("최근3개월평균(억)", ascending=False, na_position="last").reset_index(drop=True)

m1, m2, m3 = st.columns(3)
m1.metric("매칭 단지 수", f"{len(summary):,}개")
m2.metric("매칭 거래 건수", f"{len(filtered):,}건")
m3.metric("전체 데이터 규모", f"{df['aptNm'].nunique():,}개 단지 · {len(df):,}건")

st.markdown("##### 단지 목록 — 왼쪽 체크박스로 최대 8개까지 비교 선택")

filter_sig = f"{tuple(sorted(sel_regions))}|{tuple(sorted(sel_dongs))}|{tuple(sorted(sel_apts))}"
editor_key = f"editor_{abs(hash(filter_sig))}"

edited = st.data_editor(
    summary,
    key=editor_key,
    hide_index=True,
    use_container_width=True,
    height=420,
    column_config={
        "선택": st.column_config.CheckboxColumn(required=True, width="small"),
        "최근3개월평균(억)": st.column_config.NumberColumn(format="%.2f억"),
        "준공년도": st.column_config.NumberColumn(format="%d"),
    },
    disabled=[c for c in summary.columns if c != "선택"],
)

selected = edited[edited["선택"]]
if len(selected) > 8:
    st.warning("최대 8개까지 비교할 수 있어요. 상위 8개만 차트/지도에 반영합니다.")
    selected = selected.head(8)
sel_keys = list(zip(selected["지역"], selected["동"], selected["아파트명"]))

# ---------------- Trend chart ----------------
st.markdown("##### 실거래가 추이")
if sel_keys:
    tx = filtered[filtered.set_index(["지역", "umdNm", "aptNm"]).index.isin(sel_keys)].copy()
    tx["연월"] = tx["dealYear"].astype(str) + "-" + tx["dealMonth"].astype(str).str.zfill(2)
    tx["단지"] = tx["동"] if False else tx["umdNm"] + " " + tx["aptNm"]
    monthly = (
        tx.groupby(["단지", "연월"], as_index=False)["억"].mean()
        .sort_values("연월")
    )
    fig = px.line(
        monthly, x="연월", y="억", color="단지", markers=True,
        color_discrete_sequence=SERIES_COLORS,
        labels={"억": "실거래가(억원)", "연월": "계약년월"},
    )
    fig.update_traces(line=dict(width=2), marker=dict(size=7))
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("위 표에서 단지를 체크하면 여기에 시계열 실거래가 추이가 표시됩니다.")

# ---------------- Map ----------------
st.markdown("##### 선택 단지 위치")
if sel_keys:
    map_df = geo.merge(
        pd.DataFrame(sel_keys, columns=["지역", "umdNm", "aptNm"]),
        on=["지역", "umdNm", "aptNm"], how="inner",
    ).dropna(subset=["lat", "lon"])
    if len(map_df):
        map_df = map_df.reset_index(drop=True)
        map_df["color"] = [
            list(int(SERIES_COLORS[i % len(SERIES_COLORS)][j:j + 2], 16) for j in (1, 3, 5)) + [200]
            for i in range(len(map_df))
        ]
        layer = pdk.Layer(
            "ScatterplotLayer", data=map_df,
            get_position="[lon, lat]", get_fill_color="color",
            get_radius=140, radius_min_pixels=6, radius_max_pixels=24,
            pickable=True, stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=1.5,
        )
        view_state = pdk.ViewState(
            latitude=float(map_df["lat"].mean()), longitude=float(map_df["lon"].mean()),
            zoom=9.5,
        )
        st.pydeck_chart(pdk.Deck(
            layers=[layer], initial_view_state=view_state, map_style=None,
            tooltip={"html": "<b>{aptNm}</b><br/>{지역} {umdNm}<br/>{addr_display}"},
        ))
        st.caption("위치는 OpenStreetMap(Nominatim)으로 지오코딩한 근사 좌표입니다 — 정확한 위치는 지도 앱에서 재확인하세요.")
        missing = len(map_df) < len(sel_keys)
        if missing:
            st.caption(f"⚠ {len(sel_keys) - len(map_df)}개 단지는 좌표를 찾지 못해 지도에 표시되지 않았습니다.")
    else:
        st.warning("선택한 단지의 좌표를 찾지 못했습니다.")
else:
    st.info("위 표에서 단지를 체크하면 여기에 지도가 표시됩니다.")

st.divider()
st.caption(
    "데이터: 국토교통부 실거래가공개시스템 API (data.go.kr) · 정적 스냅샷이며 주기적으로 수동 갱신됩니다. "
    "세대수·학군·치안 등 정성 정보는 이 앱에 포함되어 있지 않습니다."
)
