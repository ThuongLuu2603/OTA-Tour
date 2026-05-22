import re
import requests
from bs4 import BeautifulSoup

url = "https://travel.com.vn/du-lich-viet-nam.aspx"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
print("status", r.status_code, "len", len(r.text))

soup = BeautifulSoup(r.text, "html.parser")
# tour cards
for a in soup.select("a[href]"):
    href = a.get("href", "")
    if "tour" in href.lower() or "du-lich" in href.lower():
        if href.startswith("/"):
            href = "https://travel.com.vn" + href
        if "travel.com.vn" in href and "login" not in href:
            print(href[:120])

print("--- h3 ---")
for h in soup.find_all("h3")[:8]:
    print(h.get_text(strip=True)[:80])

# JSON in page
for pat in [r"api[^\"']+", r"/tours[^\"']*", r"__NEXT_DATA__", r"window\.__"]:
    m = re.search(pat, r.text)
    if m:
        print("found pattern", pat, m.group(0)[:80])
