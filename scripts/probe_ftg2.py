import json
import re
import requests

url = "https://findtourgo.com/vi/country/china?currency=VND"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
t = r.text

# try common API patterns
candidates = [
    "https://findtourgo.com/api/tours?country=china&currency=VND",
    "https://findtourgo.com/api/v1/tours?country=china",
    "https://api.findtourgo.com/tours?country=china",
    "https://findtourgo.com/vi/api/tours?country=china&currency=VND",
]
for c in candidates:
    try:
        rr = requests.get(c, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=15)
        print(c, rr.status_code, rr.text[:200])
    except Exception as e:
        print(c, e)

# search embedded state
for pat in [r"window\.__[A-Z_]+", r"self\.__next_f", r"NUXT", r"__NUXT__", r"initialState", r"tours\s*:\s*\["]:
    if re.search(pat, t):
        print("found", pat)

# all script src
from bs4 import BeautifulSoup
soup = BeautifulSoup(t, "html.parser")
for s in soup.find_all("script", src=True):
    print("src", s["src"][:100])
