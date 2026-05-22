import re
import requests
from bs4 import BeautifulSoup

url = "https://findtourgo.com/vi/country/china?currency=VND"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
soup = BeautifulSoup(r.text, "html.parser")

# tour links
links = set()
for a in soup.find_all("a", href=True):
    h = a["href"]
    if "/vi/tours/" in h or "/tours/" in h:
        if h.startswith("/"):
            h = "https://findtourgo.com" + h
        links.add(h.split("?")[0])
print("tour links", len(links))
for l in list(links)[:5]:
    print(l)

# company names
for sel in [".tour-card", "[class*='tour']", "[class*='Tour']", "article"]:
    els = soup.select(sel)
    if els:
        print("sel", sel, len(els))

# script json
for script in soup.find_all("script"):
    t = script.string or ""
    if t and ("VN-" in t or "tourCode" in t or "operator" in t.lower()):
        if len(t) > 500:
            open(r"C:\Users\thuon\Desktop\OTA\ota-dashboard\scripts\ftg_script.txt", "w", encoding="utf-8").write(t[:50000])
            print("script len", len(t))
            break

# text patterns
print("VN codes", len(re.findall(r"VN-\d+", r.text)))
