import json
import re
import requests


def extract_escaped_json_array(text, key):
    marker = f'\\"{key}\\":'
    idx = text.find(marker)
    if idx < 0:
        marker2 = f'"{key}":'
        idx = text.find(marker2)
        if idx < 0:
            return None
        start = text.find("[", idx)
        escape = False
    else:
        start = text.find("[", idx)
        escape = True

    if start < 0:
        return None

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                raw = text[start : i + 1]
                if escape:
                    raw = raw.encode().decode("unicode_escape")
                    raw = raw.replace('\\"', '"')
                return json.loads(raw)
    return None


def extract_tours_from_page(url, thi_truong):
    text = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
    tours = []

    # Card list: pageTitle appears in listing (less escaped)
    # Find all tour card objects via pageCode + pageTitle pattern
    card_pat = re.compile(
        r'\\"pageId\\":(\d+),\\"pageCode\\":\\"([^\\"]*)\\",\\"pageTitle\\":\\"((?:\\\\.|[^\\"\\\\])*)\\"'
        r'.*?\\"linkShare\\":\\"((?:\\\\.|[^\\"\\\\])*)\\"'
        r'.*?\\"departureName\\":\\"((?:\\\\.|[^\\"\\\\])*)\\"'
        r'.*?\\"dayNight\\":\\"((?:\\\\.|[^\\"\\\\])*)\\"'
        r'.*?\\"salePrice\\":(\d+)',
        re.S,
    )
    for m in card_pat.finditer(text):
        title = m.group(3).encode().decode("unicode_escape")
        link = m.group(4).encode().decode("unicode_escape")
        dep = m.group(5).encode().decode("unicode_escape")
        duration = m.group(6).encode().decode("unicode_escape")
        price = int(m.group(7))
        tours.append({
            "page_id": m.group(1),
            "page_code": m.group(2),
            "ten_tour": title,
            "link": link,
            "diem_kh": dep,
            "thoi_gian": duration,
            "gia": price,
            "thi_truong": thi_truong,
        })

    if not tours:
        # fallback: unescaped variant
        card_pat2 = re.compile(
            r'"pageId":(\d+),"pageCode":"([^"]*)","pageTitle":"((?:\\.|[^"\\])*)"'
            r'.*?"linkShare":"((?:\\.|[^"\\])*)"'
            r'.*?"departureName":"((?:\\.|[^"\\])*)"'
            r'.*?"dayNight":"((?:\\.|[^"\\])*)"'
            r'.*?"salePrice":(\d+)',
            re.S,
        )
        for m in card_pat2.finditer(text):
            tours.append({
                "page_id": m.group(1),
                "page_code": m.group(2),
                "ten_tour": m.group(3),
                "link": m.group(4),
                "diem_kh": m.group(5),
                "thoi_gian": m.group(6),
                "gia": int(m.group(7)),
                "thi_truong": thi_truong,
            })

    # dedupe by link
    seen = set()
    unique = []
    for t in tours:
        if t["link"] not in seen:
            seen.add(t["link"])
            unique.append(t)
    return unique


dom = extract_tours_from_page(
    "https://travel.com.vn/du-lich-viet-nam.aspx", "Du lịch trong nước"
)
print("domestic", len(dom))
if dom:
    print(dom[0])

intl = extract_tours_from_page(
    "https://travel.com.vn/du-lich-nuoc-ngoai.aspx", "Du lịch nước ngoài"
)
print("international", len(intl))
