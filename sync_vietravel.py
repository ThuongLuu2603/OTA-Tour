#!/usr/bin/env python3
"""CLI: Quét tour Vietravel từ travel.com.vn và ghi lên Google Sheet."""

import argparse
import sys

from vietravel_scraper import scrape_all_vietravel_tours, write_to_google_sheet


def main():
    parser = argparse.ArgumentParser(description="Sync Vietravel tours to Google Sheets")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Chỉ quét và in thống kê, không ghi Sheet",
    )
    args = parser.parse_args()

    print("Đang quét travel.com.vn ...")
    df = scrape_all_vietravel_tours()
    print(f"Đã quét: {len(df)} tour")
    print(df["thi_truong"].value_counts().to_string())

    if args.preview:
        print("\nChế độ preview — không ghi Google Sheet.")
        return 0

    print("\nĐang ghi Google Sheet ...")
    meta = write_to_google_sheet(df)
    print("Hoàn tất:", meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
