import re
import requests


def _dec(s):
    try:
        return s.encode("utf-8").decode("unicode_escape")
    except Exception:
        return s.replace("\\u0026", "&").replace('\\"', '"')


def extract_tours_fast(url, thi_truong):
    text = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
    marker = '\\"pageId\\":'
    if marker not in text:
        marker = '"pageId":'
    chunks = text.split(marker)[1:]
    tours = []
    for chunk in chunks[:200]:
        def grab(key):
            for mk in (f'\\"{key}\\":\\"', f'"{key}":"'):
                i = chunk.find(mk)
                if i < 0:
                    continue
                start = i + len(mk)
                end = start
                esc = False
                while end < len(chunk):
                    c = chunk[end]
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        break
                    end += 1
                return _dec(chunk[start:end])
            return ""

        def grab_num(key):
            for mk in (f'\\"{key}\\":', f'"{key}":'):
                i = chunk.find(mk)
                if i >= 0:
                    m = re.match(rf"{re.escape(mk)}(\d+)", chunk[i:])
                    if m:
                        return int(m.group(1))
            return None

        link = grab("linkShare")
        title = grab("pageTitle")
        if not link or not title:
            continue
        tours.append({
            "ten_tour": title,
            "link": link,
            "diem_kh": grab("departureName"),
            "thoi_gian": grab("dayNight"),
            "gia": grab_num("salePrice"),
            "page_code": grab("pageCode"),
            "thi_truong": thi_truong,
            "tuyen_tour": thi_truong,
            "cong_ty": "Vietravel",
        })

    seen = set()
    out = []
    for t in tours:
        if t["link"] not in seen:
            seen.add(t["link"])
            out.append(t)
    return out


dom = extract_tours_fast("https://travel.com.vn/du-lich-viet-nam.aspx", "Du lịch trong nước")
print("domestic", len(dom))
if dom:
    print(dom[0])
