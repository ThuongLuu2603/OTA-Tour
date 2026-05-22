import json
import re
import requests

url = "https://travel.com.vn/du-lich-viet-nam.aspx"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
text = r.text

# chuong-trinh links
links = re.findall(
    r'https://travel\.com\.vn/chuong-trinh/[a-z0-9\-]+-pid-\d+',
    text,
    re.I,
)
links = sorted(set(links))
print("unique tour links", len(links))

# try find embedded list JSON
for key in ["tourList", "tours", "items", "departures", "products"]:
    if f'"{key}"' in text:
        print("has key", key)

# price patterns near titles
blocks = re.findall(r'"title"\s*:\s*"([^"]{10,200})"', text)
print("title json count", len(blocks))
if blocks:
    print("sample title", blocks[0][:100])

# departureDomestic or similar
m = re.search(r'"departure[^"]*"\s*:\s*(\[[\s\S]{500,50000}?\])', text)
if m:
    print("departure array len", len(m.group(1)))

# save snippet around first pid
idx = text.find("pid-4967")
if idx > 0:
    snippet = text[idx - 500 : idx + 1500]
    open(r"C:\Users\thuon\Desktop\OTA\ota-dashboard\scripts\snippet.txt", "w", encoding="utf-8").write(snippet)
