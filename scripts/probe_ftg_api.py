import json
import requests

h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
base = "https://api-v2.findtourgo.com/v1"

item = requests.get(
    f"{base}/search/tours?countryCode=CN&page=0&pageSize=1&locale=vi&currency=VND",
    headers=h,
    timeout=30,
).json()["items"][0]
print("search keys", sorted(item.keys()))
cid = item["companyId"]
dcity = item["departureCity"]

for path in [
    f"public/companies/{cid}?locale=vi",
    f"companies/{cid}",
    f"public/company/{cid}?locale=vi",
]:
    r = requests.get(f"{base}/{path}", headers=h, timeout=15)
    print(path, r.status_code, r.text[:400] if r.ok else r.text[:200])

r = requests.get(f"{base}/public/cities/{dcity}?locale=vi", headers=h, timeout=15)
print("city", r.status_code, r.text[:400])

for cc in ["CN", "JP", "VN"]:
    d = requests.get(
        f"{base}/search/tours?countryCode={cc}&page=0&pageSize=50&locale=vi&currency=VND",
        headers=h,
        timeout=30,
    ).json()
    print(
        cc,
        "items",
        len(d.get("items") or []),
        "totalPage",
        d.get("totalPage"),
        "canNext",
        d.get("canNext"),
    )
    if cc == "CN" and d.get("items"):
        it = d["items"][0]
        if "companyName" in it:
            print("companyName", it["companyName"])
