import re
import requests

url = "https://travel.com.vn/du-lich-viet-nam.aspx"
text = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
marker = '\\"pageId\\":'
chunks = text.split(marker)[1:3]
CARD_RE = re.compile(
    r'\\"pageId\\":(\d+),\\"pageCode\\":\\"([^\\"]+)\\",\\"pageTitle\\":\\"([^\\"]*)\\"'
    r'.*?\\"linkShare\\":\\"(https://travel\.com\.vn/chuong-trinh/[^\\"]+)\\"'
    r'.*?\\"departureName\\":\\"([^\\"]*)\\"'
    r'.*?\\"dayNight\\":\\"([^\\"]*)\\"',
    re.S,
)
for i, chunk in enumerate(chunks):
    block = chunk[:15000]
    m = CARD_RE.search(block)
    print("chunk", i, "match", bool(m))
    if not m:
        # what's in block start
        print(block[:300])
    else:
        print("title", m.group(3)[:60])
        print("link", m.group(4)[:80])
