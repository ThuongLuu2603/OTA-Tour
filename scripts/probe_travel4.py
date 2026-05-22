import json
import re
import requests

url = "https://travel.com.vn/du-lich-viet-nam.aspx"
text = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text

# Find listTour array - try multiple approaches
idx = text.find('"listTour"')
print("listTour idx", idx)
if idx >= 0:
    print(text[idx : idx + 200])

# Extract using regex for each tour block (pageTitle ... linkShare)
pattern = re.compile(
    r'"pageId":(\d+).*?"pageTitle":"((?:\\.|[^"\\])*)".*?'
    r'"linkShare":"((?:\\.|[^"\\])*)".*?'
    r'"departureName":"((?:\\.|[^"\\])*)".*?'
    r'"dayNight":"((?:\\.|[^"\\])*)".*?'
    r'"salePrice":(\d+)',
    re.S,
)
matches = pattern.findall(text)
print("regex matches", len(matches))
if matches:
    print("first", matches[0][:3])

# Simpler: split by pageId
parts = text.split('"pageId":')
print("pageId splits", len(parts) - 1)
