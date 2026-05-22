"""
Giá TB & số đoàn/chuyến thống nhất.

Công thức (mỗi ô Tuyến × Điểm KH):
  so_doan_i = trip_weight (số đoàn/chuyến proxy từ lịch KH)
  ngay_di_i = so_ngay × so_doan (chỉ khi có số ngày hợp lệ)

  Giá TB / đoàn  = Σ(gia × so_doan) / Σ(so_doan)
  Ngày TB / đoàn = Σ(ngày_di) / Σ(so_doan)   [chỉ SP có so_ngay]
  Giá TB / ngày  = Σ(gia × so_doan) / Σ(ngày_di)  [so sánh công bằng khi khác số ngày]
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

DAILY_HORIZON_DAYS = 90
WEEKLY_HORIZON_WEEKS = 13

# So sánh chính: tuyến + điểm khởi hành (không gộp HN với HCM)
ROUTE_DEP_COLS = ("tuyen_tour", "diem_kh_clean")

# Bảng so sánh công ty vs TT (thêm vùng thị trường)
COMPARISON_COLS = ("thi_truong", "tuyen_tour", "diem_kh_clean")

# Chi tiết thêm nhóm ngày (expander / debug)
DETAIL_SEGMENT_COLS = ("tuyen_tour", "diem_kh_clean", "nhom_thoi_gian")

# Giữ alias cho code cũ
SEGMENT_COLS = ROUTE_DEP_COLS

NHOM_THOI_ORDER = [
    "Nửa ngày",
    "1 ngày",
    "2–3 ngày",
    "4–6 ngày",
    "7+ ngày",
    "Không xác định",
]

METRIC_FOOTNOTE = (
    "**Giá TB / đoàn** = Σ(giá × đoàn) / Σ(đoàn). **Giá TB / ngày** = Σ(giá × đoàn) / Σ(ngày×đoàn). "
    "Tab Đối thủ — **Giá TB so sánh** = Giá TB/ngày × **Ngày TB/đoàn (công ty)**; "
    "TT cũng nhân ngày của công ty (cùng cơ số). "
    f"Số đoàn: lịch cố định / hàng ngày {DAILY_HORIZON_DAYS} / hàng tuần {WEEKLY_HORIZON_WEEKS}."
)


def duration_bucket(so_ngay: float | None) -> str:
    if so_ngay is None or (isinstance(so_ngay, float) and np.isnan(so_ngay)):
        return "Không xác định"
    if so_ngay <= 0.5:
        return "Nửa ngày"
    if so_ngay <= 1:
        return "1 ngày"
    if so_ngay <= 3:
        return "2–3 ngày"
    if so_ngay <= 6:
        return "4–6 ngày"
    return "7+ ngày"


def schedule_weight(lich_loai: str, ngay_kh_list: list | None) -> float:
    loai = (lich_loai or "").strip()
    dates = ngay_kh_list or []
    n_dates = len(dates) if isinstance(dates, list) else 0

    if loai == "Lịch cố định" and n_dates > 0:
        w = float(n_dates)
    elif loai == "Hàng ngày":
        w = float(DAILY_HORIZON_DAYS)
    elif loai == "Hàng tuần":
        w = float(WEEKLY_HORIZON_WEEKS)
    else:
        w = 1.0
    return max(w, 1.0)


def confidence_factor(lich_loai: str) -> float:
    loai = (lich_loai or "").strip()
    if loai == "Lịch cố định":
        return 1.0
    if loai in ("Hàng ngày", "Hàng tuần"):
        return 0.65
    return 0.35


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "so_ngay" not in out.columns:
        out["so_ngay"] = np.nan
    out["nhom_thoi_gian"] = out["so_ngay"].apply(duration_bucket)

    if "lich_loai" not in out.columns:
        out["lich_loai"] = ""
    if "ngay_kh_list" not in out.columns:
        out["ngay_kh_list"] = [[] for _ in range(len(out))]

    out["w_lich"] = [
        schedule_weight(lo, dates)
        for lo, dates in zip(out["lich_loai"], out["ngay_kh_list"])
    ]
    out["w_tin"] = out["lich_loai"].apply(confidence_factor)
    out["so_doan"] = out["w_lich"] * out["w_tin"]
    out["trip_weight"] = out["so_doan"]  # alias

    days = pd.to_numeric(out["so_ngay"], errors="coerce")
    valid = days.notna() & (days > 0)
    out["ngay_di"] = np.where(valid, days * out["so_doan"], np.nan)

    return out


def _priced(df: pd.DataFrame) -> pd.DataFrame:
    if "so_doan" not in df.columns:
        df = enrich_dataframe(df)
    return df.dropna(subset=["gia"]).copy()


def _metrics_from_group(g: pd.DataFrame) -> dict:
    """Một nhóm SP cùng ô (tuyến + điểm KH …)."""
    d = g["so_doan"].astype(float)
    so_doan = float(d.sum())
    so_sp = len(g)

    if so_doan <= 0:
        return {
            "so_doan": 0.0,
            "so_sp": so_sp,
            "tong_ngay_di": 0.0,
            "gia_tb_doan": np.nan,
            "gia_tb_ngay": np.nan,
            "ngay_tb_doan": np.nan,
            "gia_tb": np.nan,
        }

    gia_tb_doan = float((g["gia"] * d).sum() / so_doan)

    has_ngay = g["ngay_di"].notna()
    if has_ngay.any():
        tong_ngay = float(g.loc[has_ngay, "ngay_di"].sum())
        d_ngay = g.loc[has_ngay, "so_doan"].astype(float)
        so_doan_ngay = float(d_ngay.sum())
        gia_tb_ngay = float(
            (g.loc[has_ngay, "gia"] * d_ngay).sum() / tong_ngay
        ) if tong_ngay > 0 else np.nan
        ngay_tb_doan = tong_ngay / so_doan_ngay if so_doan_ngay > 0 else np.nan
    else:
        tong_ngay = 0.0
        gia_tb_ngay = np.nan
        ngay_tb_doan = np.nan

    return {
        "so_doan": so_doan,
        "so_sp": so_sp,
        "tong_ngay_di": tong_ngay,
        "gia_tb_doan": gia_tb_doan,
        "gia_tb_ngay": gia_tb_ngay,
        "ngay_tb_doan": ngay_tb_doan,
        "gia_tb": gia_tb_doan,
    }


def agg_route_dep(
    df: pd.DataFrame,
    group_cols: Iterable[str] | None = None,
    *,
    exclude_company: str | None = None,
    company: str | None = None,
) -> pd.DataFrame:
    gcols = list(group_cols or ROUTE_DEP_COLS)
    sub = _priced(df)
    if exclude_company:
        sub = sub[sub["cong_ty"] != exclude_company]
    if company:
        sub = sub[sub["cong_ty"] == company]
    if sub.empty:
        return pd.DataFrame()

    rows = []
    for keys, g in sub.groupby(gcols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        rows.append({**dict(zip(gcols, keys)), **_metrics_from_group(g)})
    return pd.DataFrame(rows)


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna() & (weights > 0)
    v = values[mask]
    w = weights[mask]
    if len(v) == 0 or w.sum() == 0:
        return np.nan
    return float(np.average(v, weights=w))


def segment_prices(
    df: pd.DataFrame,
    *,
    exclude_company: str | None = None,
    company: str | None = None,
    detail: bool = False,
) -> pd.DataFrame:
    cols = DETAIL_SEGMENT_COLS if detail else ROUTE_DEP_COLS
    out = agg_route_dep(df, cols, exclude_company=exclude_company, company=company)
    if not out.empty:
        out["so_chuyen"] = out["so_doan"]
    return out


def rollup_route(
    seg_df: pd.DataFrame,
    route_col: str = "tuyen_tour",
) -> pd.DataFrame:
    """Gom các ô (cùng tuyến, khác điểm KH) — TB theo tổng đoàn & ngày."""
    if seg_df.empty:
        return pd.DataFrame()

    rows = []
    for route, g in seg_df.groupby(route_col, dropna=False):
        w = g["so_doan"]
        if w.sum() == 0:
            continue
        m = {
            route_col: route,
            "so_doan": w.sum(),
            "so_chuyen": w.sum(),
            "so_sp": g["so_sp"].sum(),
            "so_o": len(g),
            "tong_ngay_di": g["tong_ngay_di"].sum(),
            "gia_tb_doan": weighted_mean(g["gia_tb_doan"], w),
            "gia_tb": weighted_mean(g["gia_tb_doan"], w),
        }
        tn = g["tong_ngay_di"].sum()
        if tn > 0 and g["gia_tb_ngay"].notna().any():
            # Gom lại từ tổng doanh thu proxy / tổng ngày
            num = (g["gia_tb_ngay"] * g["tong_ngay_di"]).sum()
            m["gia_tb_ngay"] = float(num / tn) if tn > 0 else np.nan
            m["ngay_tb_doan"] = float(tn / w.sum())
        else:
            m["gia_tb_ngay"] = np.nan
            m["ngay_tb_doan"] = weighted_mean(g["ngay_tb_doan"], w)
        rows.append(m)
    return pd.DataFrame(rows)


def market_route_prices(df: pd.DataFrame, exclude_company: str | None = None) -> pd.DataFrame:
    return rollup_route(segment_prices(df, exclude_company=exclude_company))


def company_route_prices(df: pd.DataFrame, company: str) -> pd.DataFrame:
    return rollup_route(segment_prices(df, company=company))


def pivot_company_route(
    df: pd.DataFrame,
    companies: list[str] | None = None,
    routes: list[str] | None = None,
    *,
    use_price_per_day: bool = True,
) -> pd.DataFrame:
    sub = _priced(df)
    if companies:
        sub = sub[sub["cong_ty"].isin(companies)]
    if routes:
        sub = sub[sub["tuyen_tour"].isin(routes)]

    price_col = "gia_tb_ngay" if use_price_per_day else "gia_tb_doan"
    rows = []
    for (co, route), g in sub.groupby(["cong_ty", "tuyen_tour"], dropna=False):
        seg = agg_route_dep(g, ROUTE_DEP_COLS)
        rolled = rollup_route(seg)
        if rolled.empty:
            continue
        val = rolled[price_col].iloc[0] if price_col in rolled.columns else rolled["gia_tb_doan"].iloc[0]
        rows.append({"cong_ty": co, "tuyen_tour": route, "gia_tb": val})
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.pivot(index="cong_ty", columns="tuyen_tour", values="gia_tb")


def sum_weighted_counts(df: pd.DataFrame, group_cols: Iterable[str]) -> pd.DataFrame:
    if "so_doan" not in df.columns:
        df = enrich_dataframe(df)
    gcols = list(group_cols)
    agg = (
        df.groupby(gcols, dropna=False)
        .agg(
            so_chuyen=("so_doan", "sum"),
            so_doan=("so_doan", "sum"),
            tong_ngay_di=("ngay_di", lambda s: float(s.sum()) if s.notna().any() else 0.0),
            so_sp=("ten_tour", "count"),
        )
        .reset_index()
    )
    return agg


def attach_segment_benchmark(
    df: pd.DataFrame,
    *,
    benchmark_df: pd.DataFrame | None = None,
    exclude_company: str | None = None,
    use_price_per_day: bool = True,
) -> pd.DataFrame:
    out = _priced(df)
    base = benchmark_df if benchmark_df is not None else df
    mkt = agg_route_dep(base, exclude_company=exclude_company)
    if mkt.empty:
        out["gia_tb_o"] = np.nan
        out["vs_pct"] = np.nan
        return out

    pcol = "gia_tb_ngay" if use_price_per_day else "gia_tb_doan"
    mkt = mkt.rename(columns={pcol: "gia_tb_o"})
    out = out.merge(
        mkt[list(ROUTE_DEP_COLS) + ["gia_tb_o"]],
        on=list(ROUTE_DEP_COLS),
        how="left",
    )
    out["vs_pct"] = np.where(
        out["gia_tb_o"].notna() & (out["gia_tb_o"] > 0),
        (out["gia"] - out["gia_tb_o"]) / out["gia_tb_o"] * 100,
        np.nan,
    )
    return out


def apply_comparable_prices(dep: pd.DataFrame) -> pd.DataFrame:
    """
    Cùng cơ số ngày (Ngày TB/đoàn của công ty) để so sánh:
      Giá TB công ty = Giá TB/ngày (CTY) × Ngày TB/đoàn (CTY)
      Giá TB TT      = Giá TB/ngày (TT)  × Ngày TB/đoàn (CTY)
    """
    out = dep.copy()
    ngay_co = out["ngay_tb_doan_co"]

    has_basis = ngay_co.notna() & (ngay_co > 0)
    out["gia_cmp_co"] = np.where(
        has_basis & out["gia_tb_ngay_co"].notna(),
        out["gia_tb_ngay_co"] * ngay_co,
        out["gia_tb_doan_co"],
    )
    out["gia_cmp_tt"] = np.where(
        has_basis & out["gia_tb_ngay_tt"].notna(),
        out["gia_tb_ngay_tt"] * ngay_co,
        out["gia_tb_doan_tt"],
    )
    out["chenh_pct"] = np.where(
        out["gia_cmp_tt"].notna() & (out["gia_cmp_tt"] > 0) & out["gia_cmp_co"].notna(),
        (out["gia_cmp_co"] - out["gia_cmp_tt"]) / out["gia_cmp_tt"] * 100,
        np.nan,
    )
    return out


def compare_company_vs_market(
    df: pd.DataFrame,
    company: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    route_dep_table: Thị trường × Tuyến × Điểm KH, giá so sánh cùng cơ số ngày (CTY).
    detail_table: thêm nhóm ngày (cùng công thức).
    """
    sub = df[df["thi_truong"].astype(str).str.strip().ne("")]
    mkt = agg_route_dep(sub, COMPARISON_COLS, exclude_company=company)
    co = agg_route_dep(sub, COMPARISON_COLS, company=company)
    if mkt.empty and co.empty:
        return pd.DataFrame(), pd.DataFrame()

    dep = apply_comparable_prices(
        mkt.merge(co, on=list(COMPARISON_COLS), how="inner", suffixes=("_tt", "_co"))
    )

    mkt_d = agg_route_dep(sub, DETAIL_SEGMENT_COLS, exclude_company=company)
    co_d = agg_route_dep(sub, DETAIL_SEGMENT_COLS, company=company)
    detail = pd.DataFrame()
    if not mkt_d.empty or not co_d.empty:
        detail = apply_comparable_prices(
            mkt_d.merge(
                co_d, on=list(DETAIL_SEGMENT_COLS), how="outer", suffixes=("_tt", "_co")
            )
        )

    return dep, detail


def global_weighted_avg_price(df: pd.DataFrame, per_day: bool = True) -> float:
    sub = _priced(df)
    if sub.empty:
        return np.nan
    m = _metrics_from_group(sub)
    return m["gia_tb_ngay"] if per_day and pd.notna(m["gia_tb_ngay"]) else m["gia_tb_doan"]
