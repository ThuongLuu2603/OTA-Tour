"""
OTA Tour Market Dashboard
Phân tích thị trường tour du lịch Việt Nam — dữ liệu từ Google Sheets.
"""

import io
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── CONSTANTS ─────────────────────────────────────────────────────────────────

SHEET_ID = "1sI34D88zsmSrN7Jf9fS3jh4aUvaep-blxnBR1CGq9eM"
GID = "1729132868"
CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/export?format=csv&gid={GID}"
)

PRIMARY = "#003580"
# Control chars invalid in Excel/XML (e.g. backspace from scraped sheet data)
_ILLEGAL_EXCEL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
SEGMENT_ORDER = [
    "Budget (< 2tr)",
    "Mid (2–5tr)",
    "Premium (5–15tr)",
    "Luxury (> 15tr)",
    "Chưa có giá",
]
PRICE_BINS = [
    ("Budget (< 2tr)", 0, 2_000_000),
    ("Mid (2–5tr)", 2_000_000, 5_000_000),
    ("Premium (5–15tr)", 5_000_000, 15_000_000),
    ("Luxury (> 15tr)", 15_000_000, float("inf")),
]

# ── DATA HELPERS ──────────────────────────────────────────────────────────────


def _sanitize_text(val):
    """Remove characters that break openpyxl / Excel export."""
    if pd.isna(val):
        return val
    if isinstance(val, str):
        return _ILLEGAL_EXCEL_RE.sub("", val).strip()
    return val


def _sanitize_df_for_excel(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].map(_sanitize_text)
    return out


def _parse_price(val):
    """'1.050.000' → 1050000. Returns None if unparseable."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("", "-", "—", "nan", "None"):
        return None
    for token in re.findall(r"[\d.,]+", s):
        clean = re.sub(r"[.,]", "", token)
        try:
            n = int(clean)
        except ValueError:
            continue
        # Handle shorthand like "1.500" meaning 1,500,000
        if 0 < n <= 5_000:
            n *= 1_000
        if 50_000 <= n <= 500_000_000:
            return n
    return None


def _clean_dep(val):
    """Normalize departure city name to canonical form."""
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return "Không xác định"
    s = str(val).lower()
    locs = []
    if any(k in s for k in ["tân sơn nhất", "tsn", "hồ chí minh", "hcm",
                              "sài gòn", "saigon", "quận 1", "gò vấp"]):
        locs.append("Hồ Chí Minh")
    if any(k in s for k in ["nội bài", "hà nội", "hanoi", "ha noi"]):
        locs.append("Hà Nội")
    if any(k in s for k in ["đà nẵng", "da nang", "dad"]):
        locs.append("Đà Nẵng")
    if any(k in s for k in ["cần thơ", "can tho"]):
        locs.append("Cần Thơ")
    if any(k in s for k in ["thừa thiên", "thành phố huế", "tp. huế", " huế"]):
        locs.append("Huế")
    if any(k in s for k in ["nha trang"]):
        locs.append("Nha Trang")
    if locs:
        return " / ".join(locs)
    raw = str(val).strip()
    return raw if raw and raw.lower() != "nan" else "Không xác định"


def _parse_duration(val):
    """'0.5 ngày' → 0.5,  '3N2D' → 3.0,  '' → None."""
    if pd.isna(val):
        return None
    s = str(val).strip().lower()
    if not s or s in ("nan", "none"):
        return None
    if "0.5" in s or "nửa" in s or "1/2" in s:
        return 0.5
    m = re.match(r"^(\d+)\s*n", s)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*ng", s)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def _classify_schedule(val):
    """Return schedule category label."""
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return "Chưa có lịch"
    s = str(val).lower()
    if re.search(r"hàng ngày|hằng ngày|daily", s):
        return "Hàng ngày"
    if re.search(r"hàng tuần|mỗi tuần|cuối tuần|thứ 7", s):
        return "Hàng tuần"
    if re.search(r"\d{1,2}[/\-.]\d{1,2}|tháng\s*\d", s):
        return "Lịch cố định"
    return "Khác"


def _year_bounds():
    """Acceptable calendar years for tour departure dates."""
    y = date.today().year
    return y - 2, y + 3


def _safe_date(y: int, mo: int, d: int, today: date | None = None):
    """Build date if year/month/day are plausible; otherwise None."""
    today = today or date.today()
    y_min, y_max = _year_bounds()
    if not (y_min <= y <= y_max and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    try:
        dt = date(y, mo, d)
    except ValueError:
        return None
    # Upcoming / recent departures only (ignore ancient or far-future typos)
    if dt < today - timedelta(days=60) or dt > today + timedelta(days=800):
        return None
    return dt


def _extract_dates(val):
    """Return sorted list of upcoming date objects from schedule string."""
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return []
    s = str(val).strip().replace("Hằng ngày", "Hàng ngày")
    today = date.today()
    results = []

    # "Tháng 6: 18, 25 năm 2026" or "Tháng 4: 30 2025"
    for m in re.finditer(
        r"Tháng\s+(\d{1,2})\s*:\s*([\d,\s]+?)(?:\s*năm\s+(\d{4}))?(?=\s*(?:Tháng|$)|\s*$)",
        s, re.IGNORECASE,
    ):
        mo = int(m.group(1))
        default_yr = int(m.group(3)) if m.group(3) else today.year
        day_blob = m.group(2)
        # "18, 25" or "30 2025"
        for dm in re.finditer(r"(\d{1,2})(?:\s+(\d{4}))?", day_blob):
            d = int(dm.group(1))
            yr = int(dm.group(2)) if dm.group(2) else default_yr
            dt = _safe_date(yr, mo, d, today)
            if dt:
                results.append(dt)

    # "18/06/2026" or "18/6/26" — require explicit year to avoid matching prices (1.050.000)
    if not results:
        for m in re.finditer(
            r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b", s
        ):
            d, mo = int(m.group(1)), int(m.group(2))
            yr = int(m.group(3))
            if yr < 100:
                yr += 2000
            dt = _safe_date(yr, mo, d, today)
            if dt:
                results.append(dt)

    return sorted(set(results))


def _price_segment(p):
    """Classify price into market segment label."""
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "Chưa có giá"
    for name, lo, hi in PRICE_BINS:
        if lo <= p < hi:
            return name
    return "Chưa có giá"


# ── DATA LOADING ──────────────────────────────────────────────────────────────


@st.cache_data(ttl=3600, show_spinner="Đang tải dữ liệu từ Google Sheets...")
def load_data() -> pd.DataFrame:
    df_raw = pd.read_csv(CSV_URL, header=0, dtype=str)
    return _transform(df_raw)


def _transform(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    cols = list(df.columns)

    # Position-based rename (robust to header text changes)
    POS_MAP = {
        0: "cong_ty",
        1: "thi_truong",
        2: "tuyen_tour",
        3: "ten_tour",
        4: "lich_trinh",
        5: "diem_kh",
        6: "thoi_gian",
        7: "gia_raw",
        8: "lich_kh",
    }
    rmap = {cols[i]: name for i, name in POS_MAP.items() if i < len(cols)}

    # Find the raw "Link" URL column (last column named "Link", not "Link tour")
    for i, c in enumerate(cols):
        if str(c).strip().lower() == "link" and i >= 10:
            rmap[cols[i]] = "link_url"
            break

    df = df.rename(columns=rmap)

    needed = [
        "cong_ty", "thi_truong", "tuyen_tour", "ten_tour",
        "lich_trinh", "diem_kh", "thoi_gian", "gia_raw", "lich_kh",
    ]
    if "link_url" in df.columns:
        needed.append("link_url")
    df = df[[c for c in needed if c in df.columns]].copy()

    # Forward-fill company name (merged cells appear blank in CSV)
    df["cong_ty"] = (
        df["cong_ty"]
        .replace(r"^\s*$", pd.NA, regex=True)
        .replace("nan", pd.NA)
        .replace("None", pd.NA)
        .ffill()
    )

    # Drop truly empty/header-repeat rows
    for col in ["ten_tour", "cong_ty"]:
        df = df[df[col].notna()]
        df = df[df[col].astype(str).str.strip().ne("")]
        df = df[df[col].astype(str).str.strip().ne("nan")]

    # Clean string fields (strip illegal control chars from scraped sheet text)
    text_cols = ["cong_ty", "thi_truong", "tuyen_tour", "ten_tour",
                 "lich_trinh", "diem_kh", "lich_kh", "thoi_gian", "link_url"]
    for col in text_cols:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.strip()
                .replace({"nan": "", "None": "", "NaN": ""})
                .map(_sanitize_text)
            )

    # Derived columns
    df["gia"] = df["gia_raw"].apply(_parse_price)
    df["diem_kh_clean"] = df["diem_kh"].apply(_clean_dep)
    df["so_ngay"] = df["thoi_gian"].apply(_parse_duration)
    df["phan_khuc"] = df["gia"].apply(_price_segment)
    df["lich_loai"] = df["lich_kh"].apply(_classify_schedule)
    df["ngay_kh_list"] = df["lich_kh"].apply(_extract_dates)

    return df.reset_index(drop=True)


# ── UTILITIES ─────────────────────────────────────────────────────────────────


def fmt_vnd(x, short: bool = False) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    if short:
        if x >= 1_000_000:
            return f"{x / 1_000_000:.1f}tr ₫"
        return f"{x / 1_000:.0f}k ₫"
    return f"{x:,.0f} ₫"


def empty_state(msg: str = "Không có dữ liệu sau khi áp dụng bộ lọc."):
    st.info(f"ℹ️ {msg}")


def _no_data(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        empty_state()
        return True
    return False


# ── SIDEBAR ───────────────────────────────────────────────────────────────────


def render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.markdown(
            f"<div style='text-align:center;padding:16px 0 8px;'>"
            f"<div style='font-size:2.4rem;'>✈️</div>"
            f"<div style='font-weight:700;font-size:1.05rem;color:{PRIMARY};'>OTA Tour Dashboard</div>"
            f"<div style='font-size:0.78rem;color:#6c757d;margin-top:3px;'>Phân tích thị trường du lịch VN</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.divider()

        if st.button("🔄 Cập nhật dữ liệu", use_container_width=True, help="Xóa cache và tải lại từ Google Sheets"):
            st.cache_data.clear()
            st.rerun()

        st.subheader("⚙️ Bộ lọc")

        def _opts(col):
            return sorted(df[col].replace("", pd.NA).dropna().unique().tolist())

        sel_mkt = st.multiselect("🗺️ Thị trường", _opts("thi_truong"))
        sel_co = st.multiselect("🏢 Công ty", _opts("cong_ty"))
        sel_route = st.multiselect("🛣️ Tuyến tour", _opts("tuyen_tour"))
        sel_dep = st.multiselect("📍 Điểm khởi hành", _opts("diem_kh_clean"))
        sel_lich = st.multiselect("📅 Loại lịch", _opts("lich_loai"))

        prices = df["gia"].dropna()
        if len(prices) >= 2:
            p_min, p_max = int(prices.min()), int(prices.max())
            p_rng = st.slider(
                "💰 Khoảng giá (VND)",
                min_value=p_min,
                max_value=p_max,
                value=(p_min, p_max),
                step=100_000,
                format="%d",
            )
        else:
            p_rng = (0, 500_000_000)

        # Apply filters
        fdf = df.copy()
        if sel_mkt:
            fdf = fdf[fdf["thi_truong"].isin(sel_mkt)]
        if sel_co:
            fdf = fdf[fdf["cong_ty"].isin(sel_co)]
        if sel_route:
            fdf = fdf[fdf["tuyen_tour"].isin(sel_route)]
        if sel_dep:
            fdf = fdf[fdf["diem_kh_clean"].isin(sel_dep)]
        if sel_lich:
            fdf = fdf[fdf["lich_loai"].isin(sel_lich)]

        # Price filter: keep rows without a price (don't exclude them)
        has_p = fdf["gia"].notna()
        fdf = fdf[~has_p | fdf["gia"].between(p_rng[0], p_rng[1])]

        st.divider()
        pct = len(fdf) / max(len(df), 1) * 100
        st.metric("Sản phẩm đang xem", f"{len(fdf):,}", f"{pct:.0f}% tổng số")

    return fdf


# ── TAB 1: TỔNG QUAN ─────────────────────────────────────────────────────────


def tab_overview(df: pd.DataFrame):
    if _no_data(df):
        return

    # ── KPI Row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Tổng sản phẩm", f"{len(df):,}")
    c2.metric("🏢 Công ty đối thủ", f"{df['cong_ty'].nunique():,}")
    c3.metric("🛣️ Tuyến tour", f"{df['tuyen_tour'].nunique():,}")
    avg_p = df["gia"].mean()
    c4.metric("💰 Giá trung bình", fmt_vnd(avg_p, short=True) if pd.notna(avg_p) else "N/A")

    st.divider()

    # ── Row 1: Thị trường & Thị phần công ty
    col1, col2 = st.columns(2)

    with col1:
        mkt = (
            df[df["thi_truong"].str.strip().ne("")]
            .groupby("thi_truong")
            .size()
            .reset_index(name="Số SP")
            .sort_values("Số SP")
        )
        fig = px.bar(
            mkt, x="Số SP", y="thi_truong", orientation="h",
            title="Số sản phẩm theo Thị trường",
            labels={"thi_truong": "Thị trường"},
            color="Số SP", color_continuous_scale="Blues",
        )
        fig.update_layout(showlegend=False, height=360, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        comp = (
            df.groupby("cong_ty").size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        top10 = comp.head(10).copy()
        rest = comp.iloc[10:]["count"].sum()
        if rest > 0:
            top10 = pd.concat(
                [top10, pd.DataFrame({"cong_ty": ["Khác"], "count": [rest]})],
                ignore_index=True,
            )
        fig = px.pie(
            top10, values="count", names="cong_ty",
            title="Thị phần sản phẩm theo Công ty (Top 10)",
            hole=0.45, color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=360, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Top Routes
    top_rt = (
        df[df["tuyen_tour"].str.strip().ne("")]
        .groupby("tuyen_tour").size()
        .reset_index(name="count")
        .nlargest(15, "count")
    )
    fig = px.bar(
        top_rt, x="tuyen_tour", y="count",
        title="Top 15 Tuyến Tour nhiều sản phẩm nhất",
        labels={"tuyen_tour": "Tuyến", "count": "Số SP"},
        color="count", color_continuous_scale="Blues",
    )
    fig.update_layout(showlegend=False, height=320, xaxis_tickangle=-35,
                      coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Scatter Giá × Thời gian
    sct = df.dropna(subset=["gia", "so_ngay"])
    sct = sct[sct["thi_truong"].str.strip().ne("")]
    if len(sct) > 0:
        fig = px.scatter(
            sct, x="so_ngay", y="gia",
            color="thi_truong",
            hover_data={"ten_tour": True, "cong_ty": True, "gia": ":,.0f"},
            title="Tương quan Giá và Thời gian chuyến (màu = Thị trường)",
            labels={"so_ngay": "Số ngày", "gia": "Giá (VND)", "thi_truong": "Thị trường"},
            opacity=0.72,
        )
        fig.update_yaxes(tickformat=",")
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 4: Phân khúc giá toàn thị trường
    seg = df.groupby("phan_khuc").size().reset_index(name="count")
    seg["phan_khuc"] = pd.Categorical(seg["phan_khuc"], categories=SEGMENT_ORDER, ordered=True)
    seg = seg.sort_values("phan_khuc")
    fig = px.bar(
        seg, x="phan_khuc", y="count",
        title="Phân bổ sản phẩm theo Phân khúc giá",
        labels={"phan_khuc": "Phân khúc", "count": "Số SP"},
        color="phan_khuc",
        color_discrete_sequence=["#2ecc71", "#3498db", "#e67e22", "#e74c3c", "#95a5a6"],
    )
    fig.update_layout(showlegend=False, height=300)
    st.plotly_chart(fig, use_container_width=True)


# ── TAB 2: PHÂN TÍCH GIÁ ─────────────────────────────────────────────────────


def tab_price(df: pd.DataFrame):
    pdf = df.dropna(subset=["gia"])
    if _no_data(pdf):
        return

    # ── Stats bar
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Thấp nhất", fmt_vnd(pdf["gia"].min(), short=True))
    c2.metric("Trung bình", fmt_vnd(pdf["gia"].mean(), short=True))
    c3.metric("Trung vị", fmt_vnd(pdf["gia"].median(), short=True))
    c4.metric("Cao nhất", fmt_vnd(pdf["gia"].max(), short=True))
    c5.metric("SP có giá", f"{len(pdf):,} / {len(df):,}")

    st.divider()

    # ── Histogram
    fig = px.histogram(
        pdf, x="gia", nbins=50,
        title="Phân phối giá toàn thị trường",
        labels={"gia": "Giá (VND)", "count": "Số SP"},
        color_discrete_sequence=[PRIMARY],
    )
    fig.update_xaxes(tickformat=",")
    fig.update_layout(height=280, bargap=0.05)
    st.plotly_chart(fig, use_container_width=True)

    # ── Box & Violin by Market
    mkt_df = pdf[pdf["thi_truong"].str.strip().ne("")]
    c1, c2 = st.columns(2)
    with c1:
        fig = px.box(
            mkt_df, x="thi_truong", y="gia",
            title="Box Plot giá theo Thị trường",
            labels={"thi_truong": "Thị trường", "gia": "Giá (VND)"},
            color="thi_truong", color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_yaxes(tickformat=",")
        fig.update_layout(showlegend=False, height=400, xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = px.violin(
            mkt_df, x="thi_truong", y="gia", box=True,
            title="Violin Plot giá theo Thị trường",
            labels={"thi_truong": "Thị trường", "gia": "Giá (VND)"},
            color="thi_truong", color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_yaxes(tickformat=",")
        fig.update_layout(showlegend=False, height=400, xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

    # ── Box by Top Routes
    top_r = pdf.groupby("tuyen_tour").size().nlargest(12).index
    rdf = pdf[pdf["tuyen_tour"].isin(top_r)]
    if len(rdf) > 0:
        fig = px.box(
            rdf, x="tuyen_tour", y="gia",
            title="Phân phối giá — Top 12 Tuyến Tour",
            labels={"tuyen_tour": "Tuyến", "gia": "Giá (VND)"},
            color="tuyen_tour",
        )
        fig.update_yaxes(tickformat=",")
        fig.update_layout(showlegend=False, height=420, xaxis_tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

    # ── Price Heatmap: Company × Route
    st.subheader("🔥 Heatmap Giá TB: Công ty × Tuyến")
    top_r_hm = pdf.groupby("tuyen_tour").size().nlargest(10).index.tolist()
    top_c_hm = pdf.groupby("cong_ty").size().nlargest(12).index.tolist()
    pivot = pdf.pivot_table(values="gia", index="cong_ty", columns="tuyen_tour", aggfunc="mean")
    pivot = pivot.loc[
        [c for c in top_c_hm if c in pivot.index],
        [r for r in top_r_hm if r in pivot.columns],
    ]
    if not pivot.empty:
        z = (pivot.values / 1_000_000).round(2)
        text = [
            [f"{v:.1f}tr" if not np.isnan(v) else "—" for v in row]
            for row in z
        ]
        fig = go.Figure(
            go.Heatmap(
                z=z,
                x=[str(c)[:22] for c in pivot.columns],
                y=pivot.index.tolist(),
                text=text,
                texttemplate="%{text}",
                colorscale="RdYlGn_r",
                colorbar=dict(title="Tr ₫"),
                hovertemplate="Công ty: %{y}<br>Tuyến: %{x}<br>Giá TB: %{text}<extra></extra>",
            )
        )
        fig.update_layout(
            title="Giá TB (triệu ₫) — ô đỏ = đắt, ô xanh = rẻ",
            height=520,
            xaxis_tickangle=-35,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Stats table
    st.subheader("📋 Thống kê giá theo Tuyến Tour")
    stats = (
        pdf.groupby("tuyen_tour")["gia"]
        .agg(SoSP="count", Min="min", Max="max", TrungBinh="mean", Median="median")
        .reset_index()
        .sort_values("SoSP", ascending=False)
    )
    stats.columns = ["Tuyến", "Số SP", "Giá Min", "Giá Max", "Giá TB", "Giá Median"]
    for col in ["Giá Min", "Giá Max", "Giá TB", "Giá Median"]:
        stats[col] = stats[col].apply(lambda x: f"{x:,.0f} ₫" if pd.notna(x) else "N/A")
    st.dataframe(stats, use_container_width=True, hide_index=True, height=380)


# ── TAB 3: THỊ TRƯỜNG ────────────────────────────────────────────────────────


def tab_market(df: pd.DataFrame):
    if _no_data(df):
        return

    # ── Treemap & Segment stacked bar
    c1, c2 = st.columns(2)
    with c1:
        tm = (
            df[df["thi_truong"].str.strip().ne("") & df["cong_ty"].str.strip().ne("")]
            .groupby(["thi_truong", "cong_ty"])
            .size()
            .reset_index(name="count")
        )
        fig = px.treemap(
            tm, path=["thi_truong", "cong_ty"], values="count",
            title="Cơ cấu sản phẩm: Thị trường → Công ty",
            color="count", color_continuous_scale="Blues",
        )
        fig.update_layout(height=440)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        seg = (
            df[df["thi_truong"].str.strip().ne("")]
            .groupby(["thi_truong", "phan_khuc"])
            .size()
            .reset_index(name="count")
        )
        fig = px.bar(
            seg, x="thi_truong", y="count", color="phan_khuc",
            barmode="stack",
            title="Phân khúc giá theo Thị trường",
            labels={"thi_truong": "Thị trường", "count": "Số SP", "phan_khuc": "Phân khúc"},
            category_orders={"phan_khuc": SEGMENT_ORDER},
        )
        fig.update_layout(height=440, xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

    # ── Duration structure by company
    dur = df.dropna(subset=["so_ngay"]).copy()
    if len(dur) > 0:
        dur["nhom_tg"] = dur["so_ngay"].apply(
            lambda x: "Nửa ngày (≤0.5)" if x <= 0.5
            else "1 ngày" if x <= 1
            else "2–3 ngày" if x <= 3
            else "4+ ngày"
        )
        top_co = df.groupby("cong_ty").size().nlargest(12).index
        dur_agg = (
            dur[dur["cong_ty"].isin(top_co)]
            .groupby(["cong_ty", "nhom_tg"])
            .size()
            .reset_index(name="count")
        )
        fig = px.bar(
            dur_agg, x="cong_ty", y="count", color="nhom_tg", barmode="stack",
            title="Cơ cấu sản phẩm theo Thời gian chuyến (Top 12 Công ty)",
            labels={"cong_ty": "Công ty", "count": "Số SP", "nhom_tg": "Thời gian"},
            category_orders={"nhom_tg": ["Nửa ngày (≤0.5)", "1 ngày", "2–3 ngày", "4+ ngày"]},
        )
        fig.update_layout(height=380, xaxis_tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

    # ── Avg price by company × market
    pdf = df.dropna(subset=["gia"])
    if len(pdf) > 0:
        top_co2 = pdf.groupby("cong_ty").size().nlargest(10).index
        avg_p = (
            pdf[pdf["cong_ty"].isin(top_co2) & pdf["thi_truong"].str.strip().ne("")]
            .groupby(["cong_ty", "thi_truong"])["gia"]
            .mean()
            .reset_index()
        )
        avg_p["gia_m"] = avg_p["gia"] / 1_000_000
        fig = px.bar(
            avg_p, x="cong_ty", y="gia_m", color="thi_truong", barmode="group",
            title="Giá TB theo Công ty × Thị trường (triệu ₫)",
            labels={"cong_ty": "Công ty", "gia_m": "Giá TB (tr ₫)", "thi_truong": "Thị trường"},
        )
        fig.update_layout(height=380, xaxis_tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

    # ── Departure city breakdown
    dep = (
        df[df["diem_kh_clean"].ne("Không xác định")]
        .groupby("diem_kh_clean").size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    if len(dep) > 0:
        fig = px.bar(
            dep, x="diem_kh_clean", y="count",
            title="Phân bổ sản phẩm theo Điểm khởi hành",
            labels={"diem_kh_clean": "Điểm khởi hành", "count": "Số SP"},
            color="count", color_continuous_scale="Teal",
        )
        fig.update_layout(showlegend=False, height=300, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── Route count by market (bubble)
    rt_mkt = (
        df[df["thi_truong"].str.strip().ne("") & df["tuyen_tour"].str.strip().ne("")]
        .groupby(["thi_truong", "tuyen_tour"])
        .agg(so_sp=("ten_tour", "count"), gia_tb=("gia", "mean"))
        .reset_index()
    )
    if len(rt_mkt) > 0 and rt_mkt["gia_tb"].notna().sum() > 0:
        fig = px.scatter(
            rt_mkt.dropna(subset=["gia_tb"]),
            x="thi_truong", y="gia_tb",
            size="so_sp", color="thi_truong",
            hover_data={"tuyen_tour": True, "so_sp": True, "gia_tb": ":,.0f"},
            title="Tuyến Tour: Giá TB vs Số SP (kích thước = số sản phẩm)",
            labels={"thi_truong": "Thị trường", "gia_tb": "Giá TB (VND)"},
        )
        fig.update_yaxes(tickformat=",")
        fig.update_layout(height=360, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


# ── TAB 4: ĐỐI THỦ ───────────────────────────────────────────────────────────


def tab_competitor(df: pd.DataFrame):
    if _no_data(df):
        return

    companies = sorted(df["cong_ty"].replace("", pd.NA).dropna().unique().tolist())
    if not companies:
        empty_state("Không có dữ liệu công ty.")
        return

    sel = st.selectbox("🏢 Chọn công ty để phân tích:", companies)
    cdf = df[df["cong_ty"] == sel].copy()

    # ── Metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Sản phẩm", len(cdf))
    c2.metric("Tuyến", cdf["tuyen_tour"].nunique())
    c3.metric("Thị trường", cdf["thi_truong"].nunique())
    pdata = cdf["gia"].dropna()
    c4.metric("Giá min", fmt_vnd(pdata.min(), short=True) if len(pdata) > 0 else "N/A")
    c5.metric("Giá max", fmt_vnd(pdata.max(), short=True) if len(pdata) > 0 else "N/A")

    st.divider()

    # ── Products by route & segment
    col1, col2 = st.columns(2)
    with col1:
        rc = (
            cdf[cdf["tuyen_tour"].str.strip().ne("")]
            .groupby("tuyen_tour").size()
            .reset_index(name="count")
            .sort_values("count")
        )
        fig = px.bar(
            rc, x="count", y="tuyen_tour", orientation="h",
            title=f"Sản phẩm theo Tuyến — {sel}",
            labels={"count": "Số SP", "tuyen_tour": "Tuyến"},
            color="count", color_continuous_scale="Blues",
        )
        fig.update_layout(showlegend=False, height=360, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        sc = cdf.groupby("phan_khuc").size().reset_index(name="count")
        fig = px.pie(
            sc, values="count", names="phan_khuc",
            title=f"Phân khúc giá — {sel}",
            hole=0.45, color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)

    # ── Price positioning vs route market average
    all_pdf = df.dropna(subset=["gia"])
    comp_pdf = cdf.dropna(subset=["gia"]).copy()
    if len(comp_pdf) > 0 and len(all_pdf) > 0:
        route_avg = all_pdf.groupby("tuyen_tour")["gia"].mean()
        comp_pdf["route_avg"] = comp_pdf["tuyen_tour"].map(route_avg)
        comp_pdf = comp_pdf.dropna(subset=["route_avg"])
        comp_pdf["vs_pct"] = (
            (comp_pdf["gia"] - comp_pdf["route_avg"]) / comp_pdf["route_avg"] * 100
        )
        comp_pdf["cat"] = comp_pdf["vs_pct"].apply(
            lambda x: "Rẻ hơn TB >10%" if x < -10
            else "Đắt hơn TB >10%" if x > 10
            else "Ngang giá TB (±10%)"
        )
        CLR = {
            "Rẻ hơn TB >10%": "#198754",
            "Đắt hơn TB >10%": "#dc3545",
            "Ngang giá TB (±10%)": "#fd7e14",
        }
        fig = px.scatter(
            comp_pdf, x="tuyen_tour", y="vs_pct", color="cat",
            color_discrete_map=CLR,
            hover_data={"ten_tour": True, "gia": ":,.0f", "route_avg": ":,.0f"},
            title=f"Định vị giá so với Giá TB tuyến — {sel}",
            labels={"tuyen_tour": "Tuyến", "vs_pct": "% so với giá TB tuyến", "cat": ""},
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.6)
        fig.add_hline(y=10, line_dash="dot", line_color="#dc3545", opacity=0.4)
        fig.add_hline(y=-10, line_dash="dot", line_color="#198754", opacity=0.4)
        fig.update_layout(height=380, xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

    # ── Comparison table: this company vs market by route
    if len(all_pdf) > 0 and len(comp_pdf) > 0:
        shared = list(set(cdf["tuyen_tour"].unique()) & set(all_pdf["tuyen_tour"].unique()))
        if shared:
            comp_avgs = cdf.dropna(subset=["gia"]).groupby("tuyen_tour")["gia"].mean()
            mkt_avgs = all_pdf.groupby("tuyen_tour")["gia"].mean()
            rows = []
            for r in shared:
                ca = comp_avgs.get(r, np.nan)
                ma = mkt_avgs.get(r, np.nan)
                if pd.notna(ca) and pd.notna(ma):
                    rows.append({
                        "Tuyến": r,
                        f"Giá TB {sel}": f"{ca:,.0f} ₫",
                        "Giá TB Thị trường": f"{ma:,.0f} ₫",
                        "Chênh lệch": f"{(ca - ma) / ma * 100:+.1f}%",
                    })
            if rows:
                st.subheader(f"📊 So sánh giá TB theo Tuyến — {sel} vs Thị trường")
                st.dataframe(
                    pd.DataFrame(rows).sort_values("Tuyến"),
                    use_container_width=True, hide_index=True,
                )

    # ── All products table
    st.subheader(f"📋 Tất cả sản phẩm của {sel} ({len(cdf)})")
    show_cols = ["ten_tour", "thi_truong", "tuyen_tour", "diem_kh_clean",
                 "thoi_gian", "gia", "lich_kh", "phan_khuc"]
    show = cdf[[c for c in show_cols if c in cdf.columns]].copy()
    show["gia"] = show["gia"].apply(lambda x: f"{x:,.0f} ₫" if pd.notna(x) else "N/A")
    col_map = {
        "ten_tour": "Tên Tour", "thi_truong": "Thị trường", "tuyen_tour": "Tuyến",
        "diem_kh_clean": "Điểm KH", "thoi_gian": "Thời gian",
        "gia": "Giá", "lich_kh": "Lịch KH", "phan_khuc": "Phân khúc",
    }
    show = show.rename(columns=col_map)
    col_cfg = {}
    if "link_url" in cdf.columns:
        show["Link"] = cdf["link_url"].values
        col_cfg["Link"] = st.column_config.LinkColumn("Link Tour", display_text="🔗 Xem")
    st.dataframe(show, use_container_width=True, hide_index=True,
                 height=420, column_config=col_cfg)


# ── TAB 5: LỊCH KHỞI HÀNH ────────────────────────────────────────────────────


def tab_schedule(df: pd.DataFrame):
    if _no_data(df):
        return

    # ── Schedule type donut + weekday bar
    lich_agg = df["lich_loai"].value_counts().reset_index()
    lich_agg.columns = ["Loại lịch", "Số SP"]

    c1, c2 = st.columns([1, 2])
    with c1:
        fig = px.pie(
            lich_agg, values="Số SP", names="Loại lịch",
            title="Phân loại lịch khởi hành",
            hole=0.45, color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)

    # Expand rows with specific dates
    rows = []
    for _, row in df.iterrows():
        for d in row.get("ngay_kh_list", []):
            rows.append({
                "date": d,
                "cong_ty": row["cong_ty"],
                "tuyen_tour": row["tuyen_tour"],
                "ten_tour": row["ten_tour"],
                "thi_truong": row["thi_truong"],
            })

    ddf = pd.DataFrame()
    if rows:
        ddf = pd.DataFrame(rows)
        ddf["date"] = pd.to_datetime(ddf["date"], errors="coerce")
        ddf = ddf.dropna(subset=["date"])
        y_min, y_max = _year_bounds()
        ddf = ddf[
            (ddf["date"].dt.year >= y_min) & (ddf["date"].dt.year <= y_max)
        ]

    if not ddf.empty:
        ddf["weekday"] = ddf["date"].dt.weekday
        today = date.today()

        with c2:
            dow = ddf["weekday"].value_counts().reindex(range(7), fill_value=0)
            labels = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
            fig = px.bar(
                x=labels, y=dow.values,
                title="Số chuyến khởi hành theo Ngày trong tuần",
                labels={"x": "Ngày", "y": "Số chuyến"},
                color=dow.values, color_continuous_scale="Blues",
            )
            fig.update_layout(showlegend=False, height=320, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        # ── Calendar Heatmap
        horizon = today + timedelta(days=120)
        daily = ddf.groupby("date").size().reset_index(name="count")
        date_range = pd.DataFrame({"date": pd.date_range(today, horizon)})
        cal = date_range.merge(daily, on="date", how="left")
        cal["count"] = cal["count"].fillna(0)
        cal["isoweek"] = cal["date"].dt.isocalendar().week.astype(int)
        cal["weekday"] = cal["date"].dt.weekday
        pivot_cal = (
            cal.pivot_table(index="weekday", columns="isoweek", values="count", aggfunc="sum")
            .fillna(0)
        )
        day_labels = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        fig = go.Figure(
            go.Heatmap(
                z=pivot_cal.values,
                x=pivot_cal.columns.tolist(),
                y=day_labels[: len(pivot_cal.index)],
                colorscale="YlOrRd",
                showscale=True,
                colorbar=dict(title="Số chuyến"),
                hovertemplate="Tuần %{x} — %{y}<br>Số chuyến: %{z}<extra></extra>",
            )
        )
        fig.update_layout(
            title="📅 Calendar Heatmap — Số chuyến khởi hành (120 ngày tới)",
            height=280, xaxis_title="Tuần trong năm",
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Monthly bar
        ddf["month"] = ddf["date"].dt.to_period("M").astype(str)
        month_agg = (
            ddf.groupby(["month", "thi_truong"]).size().reset_index(name="count")
        )
        fig = px.bar(
            month_agg, x="month", y="count", color="thi_truong", barmode="stack",
            title="Số chuyến khởi hành theo Tháng × Thị trường",
            labels={"month": "Tháng", "count": "Số chuyến", "thi_truong": "Thị trường"},
        )
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)

        # ── Upcoming 30 days table
        st.subheader("📆 Lịch khởi hành sắp tới (30 ngày)")
        cutoff = pd.Timestamp(today + timedelta(days=30))
        upcoming = ddf[ddf["date"] <= cutoff].sort_values("date").copy()
        if len(upcoming) > 0:
            upcoming["Ngày KH"] = upcoming["date"].dt.strftime("%d/%m/%Y")
            disp = upcoming[["Ngày KH", "cong_ty", "thi_truong", "tuyen_tour", "ten_tour"]]
            disp.columns = ["Ngày KH", "Công ty", "Thị trường", "Tuyến", "Tên Tour"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
        else:
            st.info("Không có chuyến nào có lịch cụ thể trong 30 ngày tới.")

        # ── Company schedule count
        co_sch = (
            ddf.groupby("cong_ty").size()
            .reset_index(name="Số chuyến có lịch")
            .sort_values("Số chuyến có lịch", ascending=False)
        )
        fig = px.bar(
            co_sch, x="cong_ty", y="Số chuyến có lịch",
            title="Số chuyến có lịch cố định theo Công ty",
            color="Số chuyến có lịch", color_continuous_scale="Blues",
        )
        fig.update_layout(showlegend=False, height=300, xaxis_tickangle=-30,
                          coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    else:
        with c2:
            st.info("Không có ngày khởi hành cụ thể trong bộ dữ liệu hiện tại.")

    # ── Daily products summary
    daily_df = df[df["lich_loai"] == "Hàng ngày"]
    if len(daily_df) > 0:
        st.subheader(f"✅ Sản phẩm chạy Hàng ngày ({len(daily_df)})")
        ds = daily_df[["cong_ty", "thi_truong", "tuyen_tour", "ten_tour", "gia"]].copy()
        ds["gia"] = ds["gia"].apply(lambda x: f"{x:,.0f} ₫" if pd.notna(x) else "N/A")
        ds.columns = ["Công ty", "Thị trường", "Tuyến", "Tên Tour", "Giá"]
        st.dataframe(ds, use_container_width=True, hide_index=True)


# ── TAB 6: DỮ LIỆU ───────────────────────────────────────────────────────────


def tab_data(df: pd.DataFrame):
    if _no_data(df):
        return

    # Build display dataframe
    base = ["cong_ty", "thi_truong", "tuyen_tour", "ten_tour",
            "diem_kh_clean", "thoi_gian", "gia", "lich_kh", "phan_khuc", "lich_loai"]
    out = df[[c for c in base if c in df.columns]].copy()
    out["Giá (VND)"] = out["gia"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "")
    out = out.drop(columns=["gia"])
    if "link_url" in df.columns:
        out["Link"] = df["link_url"].values

    out = out.rename(columns={
        "cong_ty": "Công ty", "thi_truong": "Thị trường", "tuyen_tour": "Tuyến",
        "ten_tour": "Tên Tour", "diem_kh_clean": "Điểm KH", "thoi_gian": "Thời gian",
        "lich_kh": "Lịch KH", "phan_khuc": "Phân khúc", "lich_loai": "Loại lịch",
    })

    # Reorder columns
    col_order = ["Công ty", "Thị trường", "Tuyến", "Tên Tour",
                 "Điểm KH", "Thời gian", "Giá (VND)", "Lịch KH", "Phân khúc", "Loại lịch"]
    if "Link" in out.columns:
        col_order.append("Link")
    out = out[[c for c in col_order if c in out.columns]]

    # ── Summary & Download row
    ca, cb, cc = st.columns([3, 1, 1])
    with ca:
        st.markdown(
            f"**{len(out):,}** sản phẩm &nbsp;|&nbsp; "
            f"**{df['cong_ty'].nunique()}** công ty &nbsp;|&nbsp; "
            f"**{df['tuyen_tour'].nunique()}** tuyến",
            unsafe_allow_html=True,
        )
    with cb:
        csv_bytes = out.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "📥 Tải CSV", data=csv_bytes,
            file_name=f"ota_{date.today()}.csv",
            mime="text/csv", use_container_width=True,
        )
    with cc:
        buf = io.BytesIO()
        out_xl = _sanitize_df_for_excel(out)
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            out_xl.to_excel(writer, index=False, sheet_name="Tour Data")
        st.download_button(
            "📊 Tải Excel", data=buf.getvalue(),
            file_name=f"ota_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    col_cfg = {}
    if "Link" in out.columns:
        col_cfg["Link"] = st.column_config.LinkColumn("Link Tour", display_text="🔗 Xem")

    st.dataframe(out, use_container_width=True, hide_index=True,
                 height=620, column_config=col_cfg)


# ── TAB 7: VIETRAVEL SYNC ─────────────────────────────────────────────────────


def tab_vietravel_sync():
    st.subheader("🔄 Quét tour Vietravel → Google Sheets")
    st.caption(
        "Nguồn: [Du lịch trong nước](https://travel.com.vn/du-lich-viet-nam.aspx) · "
        "[Du lịch nước ngoài](https://travel.com.vn/du-lich-nuoc-ngoai.aspx) → "
        f"[Sheet Vietravel](https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=620817544)"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        preview_only = st.button("🔍 Quét thử (xem trước)", use_container_width=True)
    with col_b:
        sync_sheet = st.button(
            "💾 Quét & Lưu lên Google Sheet",
            type="primary",
            use_container_width=True,
        )

    with st.expander("⚙️ Cấu hình Google Service Account"):
        st.markdown(
            """
1. Vào [Google Cloud Console](https://console.cloud.google.com/) → tạo project → bật **Google Sheets API**.
2. Tạo **Service Account** → tải file JSON key → đặt tên `credentials.json` cạnh `streamlit_app.py`.
3. Mở Google Sheet → **Chia sẻ** → thêm email Service Account (dạng `xxx@xxx.iam.gserviceaccount.com`) quyền **Editor**.
4. (Streamlit Cloud) Dán nội dung JSON vào `.streamlit/secrets.toml`:

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
client_email = "..."
client_id = "..."
```
            """
        )

    if preview_only or sync_sheet:
        with st.spinner("Đang quét travel.com.vn (trong nước + nước ngoài)..."):
            try:
                from vietravel_scraper import scrape_all_vietravel_tours, write_to_google_sheet

                vdf = scrape_all_vietravel_tours()
            except Exception as exc:
                st.error(f"Lỗi khi quét: {exc}")
                return

        if vdf.empty:
            st.warning("Không quét được tour nào. Vui lòng thử lại sau.")
            return

        c1, c2, c3 = st.columns(3)
        c1.metric("Tổng tour", len(vdf))
        c2.metric("Thị trường", vdf["thi_truong"].nunique())
        c3.metric("Tuyến tour", vdf["tuyen_tour"].nunique())

        show = vdf[
            ["ten_tour", "thi_truong", "diem_kh", "thoi_gian", "gia", "lich_kh", "link_url"]
        ].rename(
            columns={
                "ten_tour": "Tên Tour",
                "thi_truong": "Thị trường",
                "diem_kh": "Điểm KH",
                "thoi_gian": "Thời gian",
                "gia": "Giá",
                "lich_kh": "Lịch KH",
                "link_url": "Link",
            }
        )
        st.dataframe(
            show,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "Link": st.column_config.LinkColumn("Link", display_text="🔗 Xem"),
            },
        )

        if sync_sheet:
            with st.spinner("Đang ghi dữ liệu lên Google Sheet..."):
                try:
                    meta = write_to_google_sheet(vdf)
                    meta["tours_scraped"] = len(vdf)
                    st.success(
                        f"Đã lưu **{meta['rows_written']}** tour vào sheet "
                        f"**{meta['sheet_title']}** (gid={meta['gid']})."
                    )
                    st.json(meta)
                    st.cache_data.clear()
                except FileNotFoundError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Lỗi ghi Sheet: {exc}")


# ── MAIN ──────────────────────────────────────────────────────────────────────


def main():
    st.set_page_config(
        page_title="OTA Tour Dashboard",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        .block-container { padding-top: 0.8rem !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 6px; }
        .stTabs [data-baseweb="tab"] {
            background: #f0f2f6;
            border-radius: 8px 8px 0 0;
            padding: 8px 18px;
            font-weight: 500;
        }
        .stTabs [aria-selected="true"] {
            background: #003580 !important;
            color: white !important;
        }
        [data-testid="stMetric"] {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 12px 16px;
            border-left: 4px solid #003580;
        }
        .dash-banner {
            background: linear-gradient(135deg, #003580 0%, #0057b8 100%);
            color: white;
            padding: 18px 24px;
            border-radius: 12px;
            margin-bottom: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='dash-banner'>"
        "<h2 style='margin:0;color:white;'>✈️ OTA Tour Market Dashboard</h2>"
        "<p style='margin:5px 0 0;opacity:0.85;'>"
        "Phân tích thị trường tour du lịch Việt Nam — dữ liệu trực tiếp từ Google Sheets</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Load data
    try:
        df = load_data()
    except Exception as exc:
        st.error(f"❌ Không thể tải dữ liệu: {exc}")
        st.info(
            "Kiểm tra: (1) Kết nối Internet, "
            "(2) Google Sheet đã set **Anyone with link → Viewer**."
        )
        return

    if df is None or df.empty:
        st.error("Dữ liệu trống hoặc không đọc được. Vui lòng kiểm tra Google Sheet.")
        return

    # ── Sidebar filters → filtered dataframe
    fdf = render_sidebar(df)

    # ── Tabs
    t1, t2, t3, t4, t5, t6, t7 = st.tabs([
        "📊 Tổng Quan",
        "💰 Phân Tích Giá",
        "🗺️ Thị Trường",
        "🏢 Đối Thủ",
        "📅 Lịch Khởi Hành",
        "📋 Dữ Liệu",
        "🔄 Vietravel",
    ])

    with t1:
        tab_overview(fdf)
    with t2:
        tab_price(fdf)
    with t3:
        tab_market(fdf)
    with t4:
        tab_competitor(fdf)
    with t5:
        tab_schedule(fdf)
    with t6:
        tab_data(fdf)
    with t7:
        tab_vietravel_sync()


if __name__ == "__main__":
    main()
