import json
import re
import requests

url = "https://travel.com.vn/du-lich-viet-nam.aspx"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
text = r.text

# Next.js data
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
if m:
    data = json.loads(m.group(1))
    with open(r"C:\Users\thuon\Desktop\OTA\ota-dashboard\scripts\next_data_domestic.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)[:500000]
    print("NEXT_DATA keys", data.keys())
    props = data.get("props", {})
    print("props keys", props.keys())
    page_props = props.get("pageProps", {})
    print("pageProps keys", list(page_props.keys())[:20])
else:
    print("no __NEXT_DATA__")

# tourCode snippets
codes = re.findall(r'"tourCode"\s*:\s*"([^"]+)"', text)
print("tourCode count", len(codes), "sample", codes[:5])

# urls in json
urls = re.findall(r'"(https://travel\.com\.vn/[^"]+)"', text)
tour_urls = [u for u in urls if "tour" in u.lower() or "du-lich" in u.lower()]
print("urls sample", tour_urls[:10])
