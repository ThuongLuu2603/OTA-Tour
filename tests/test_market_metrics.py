"""Tests for weighted market metrics."""

import pandas as pd

from market_metrics import (
    enrich_dataframe,
    rollup_route,
    schedule_weight,
    segment_prices,
    weighted_mean,
)


def test_schedule_weight_fixed_dates():
    w = schedule_weight("Lịch cố định", [__import__("datetime").date(2026, 6, 1)] * 5)
    assert w == 5.0


def test_schedule_weight_daily():
    w = schedule_weight("Hàng ngày", [])
    assert w == 90.0


def test_weighted_mean_uses_trip_weight():
    df = enrich_dataframe(pd.DataFrame({
        "cong_ty": ["A", "A"],
        "tuyen_tour": ["R", "R"],
        "diem_kh_clean": ["Hà Nội", "Hà Nội"],
        "so_ngay": [3.0, 3.0],
        "lich_loai": ["Lịch cố định", "Lịch cố định"],
        "ngay_kh_list": [[], []],
        "gia": [10_000_000, 20_000_000],
        "ten_tour": ["t1", "t2"],
        "lich_kh": ["", ""],
    }))
    df.loc[0, "ngay_kh_list"] = [__import__("datetime").date(2026, 7, 1)] * 10
    df.loc[1, "ngay_kh_list"] = [__import__("datetime").date(2026, 7, 2)]
    df = enrich_dataframe(df)
    seg = segment_prices(df)
    rolled = rollup_route(seg)
    assert rolled["gia_tb"].iloc[0] < 15_000_000
