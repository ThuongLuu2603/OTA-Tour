#!/usr/bin/env python3
"""CLI: Quét tour FindTourGo (Trung Quốc / Nhật Bản / Việt Nam) và ghi Google Sheet."""

import argparse
import sys

from findtourgo_scraper import scrape_all_findtourgo_tours, write_to_google_sheet


def main():
    parser = argparse.ArgumentParser(
        description="Sync FindTourGo tours (CN, JP, VN) to Google Sheets"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Chỉ quét và in thống kê, không ghi Sheet",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge theo mã tour thay vì ghi đè toàn bộ tab",
    )
    parser.add_argument(
        "--countries",
        nargs="*",
        help="Chỉ quét mã quốc gia chỉ định (vd: CN JP VN)",
    )
    args = parser.parse_args()

    print("Đang quét FindTourGo (toàn bộ quốc gia có tour) ...")
    df = scrape_all_findtourgo_tours(country_codes=args.countries or None)
    print(f"Đã quét: {len(df)} tour · {df['cong_ty'].nunique()} công ty")
    print(df["thi_truong"].value_counts().head(15).to_string())
    print("\nTop công ty:")
    print(df["cong_ty"].value_counts().head(10).to_string())

    if args.preview:
        print("\nChế độ preview — không ghi Google Sheet.")
        return 0

    print("\nĐang ghi Google Sheet ...")
    meta = write_to_google_sheet(df, merge_existing=args.merge)
    print("Hoàn tất:", meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
