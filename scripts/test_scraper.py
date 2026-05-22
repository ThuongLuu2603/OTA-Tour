import sys
sys.stdout.reconfigure(encoding="utf-8")
from vietravel_scraper import scrape_all_vietravel_tours

df = scrape_all_vietravel_tours()
print("total", len(df))
print(df["thi_truong"].value_counts().to_string())
print("--- sample ---")
r = df.iloc[0]
for c in ["ten_tour", "diem_kh", "thoi_gian", "gia", "lich_kh", "link_url"]:
    print(c, ":", r[c][:120] if isinstance(r[c], str) else r[c])
