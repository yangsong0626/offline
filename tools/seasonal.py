"""Seasonal, long-running attractions (docs/seasonal.json): holiday lights, markets, rinks, shows, exhibitions.

Each item runs from "start" (null = already open) to "end". Optional:
  "days":   [5, 6, 0]       weekdays it is open (JavaScript numbering, 0 = Sunday); null = every day of the run
  "closed": ["2026-12-25"]  dates it is closed
docs/index.html (seasonOpen) decides which items are open in the current week; the guide pages list the whole season.
"""
import html, json
from datetime import date

CATS = [("lights", "✨ 灯光秀", "✨ Light shows"), ("market", "🎁 节日市集", "🎁 Holiday markets"),
        ("rink", "⛸️ 溜冰", "⛸️ Skating"), ("train", "🚂 节日小火车", "🚂 Holiday trains"),
        ("show", "🎭 节日演出 & 乐园", "🎭 Holiday shows & parks"), ("parade", "⛵ 巡游", "⛵ Parades"),
        ("exhibit", "🖼️ 展览", "🖼️ Exhibitions")]
WD_ZH = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
WD_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def esc(s): return html.escape(str(s or ""), quote=True)
def for_city(items, cid, today):
    """Items for a city that haven't ended yet, open ones first, then by start date."""
    xs = [x for x in items if x["city"] == cid and x["end"] >= today]
    return sorted(xs, key=lambda x: ((x.get("start") or "") > today, x.get("start") or "", x["end"]))

def md(iso, lang):
    d = date.fromisoformat(iso)
    return f"{d.month}/{d.day}" if lang == "zh" else f"{MON[d.month-1]} {d.day}"

def run_text(x, lang):
    zh = lang == "zh"
    if not x.get("start"): s = ("展至 " if zh else "Through ") + md(x["end"], lang)
    else: s = f'{md(x["start"], lang)}–{md(x["end"], lang)}'
    if x.get("days"):
        wd = WD_ZH if zh else WD_EN
        s += " · " + ("每" if zh else "") + ("、" if zh else ", ").join(wd[i] for i in x["days"])
    return s

def guide_url_for(page_url, cid, lang, slug): return page_url(cid, lang) + f"guides/{slug}/"

def guide_html(cid, city, items, lang, data, season, page_url, image, alt_urls):
    zh = lang == "zh"
    cname = city["zh"] if zh else city["en"]
    slug, year = season["slug"], season["year"]
    page = guide_url_for(page_url, cid, lang, slug)
    city_page = page_url(cid, lang)
    h1 = (f"{cname} {year} {season['zh']}灯光秀、节日市集、溜冰场全攻略" if zh
          else f"{cname} {season['en']} {year}: Holiday Lights, Markets & Skating")
    title = h1 + (" · 周末不无聊" if zh else " · No Boring Weekends")
    n = len(items)
    desc = (f"{cname}这个{season['zh']}的 {n} 个季节限定好去处：灯光秀、圣诞市集、溜冰场、节日演出和展览，附开放日期、时间和票价。更新于 {data['updated']}。" if zh
            else f"{n} seasonal things to do in {cname} this {season['en'].lower()}: holiday lights, markets, skating, shows and exhibitions, with dates, hours and prices. Updated {data['updated']}.")
    t = lambda x, f: x.get(f"{f}_{lang}") or x.get(f"{f}_zh") or ""
    def item(x):
        tag = ""
        if x["tier"] == "A": tag = f' <span class="tag">{"华人社区" if zh else "Chinese community"}</span>'
        elif x["tier"] == "B": tag = f' <span class="tag">{"亚裔文化" if zh else "Asian culture"}</span>'
        cost = ("免费" if zh else "Free") if x.get("free") else t(x, "cost")
        return (f'<article class="item" id="{esc(x["id"])}"><h3>{esc(t(x, "title"))}{tag}</h3>'
                f'<p class="when">🗓 {esc(run_text(x, lang))}</p><p class="who">🕒 {esc(t(x, "hours"))} · 💵 {esc(cost)}</p>'
                f'<p class="where">📍 {esc(x["venue"])} · {esc(x["address"])}</p><p>{esc(t(x, "desc"))}</p>'
                f'<p><a href="{esc(x["url"])}" target="_blank" rel="noopener">{"官网 / 详情" if zh else "Official info"} ↗</a></p></article>')
    sections = ""
    for key, hz, he in CATS:
        xs = [x for x in items if x["cat"] == key]
        if xs: sections += f"<h2>{hz if zh else he}</h2>" + "".join(item(x) for x in xs)
    events = []
    for x in items:
        if not x.get("start"): continue
        events.append({"@type": "Event", "name": t(x, "title"), "startDate": x["start"], "endDate": x["end"],
                       "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode", "eventStatus": "https://schema.org/EventScheduled",
                       "location": {"@type": "Place", "name": x["venue"], "address": x["address"]},
                       "description": t(x, "desc"), "url": x["url"], "image": [image],
                       "isAccessibleForFree": bool(x.get("free"))})
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "Article", "@id": page + "#article", "headline": title, "description": desc, "inLanguage": "zh-CN" if zh else "en",
         "dateModified": data["updated"], "image": [image], "mainEntityOfPage": page,
         "author": {"@type": "Organization", "name": "周末不无聊 No Boring Weekends"}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "周末不无聊" if zh else "No Boring Weekends", "item": page_url(None, lang)},
            {"@type": "ListItem", "position": 2, "name": cname, "item": city_page},
            {"@type": "ListItem", "position": 3, "name": (season["zh"] + "攻略") if zh else season["en"] + " guide", "item": page}]},
        *events]}
    root = "../" * (3 + (0 if zh else 1))
    alts = "".join(f'<link rel="alternate" hreflang="{h}" href="{esc(u)}">' for h, u in alt_urls)
    other = (f'<a href="{esc(alt_urls[1][1])}">English</a>' if zh else f'<a href="{esc(alt_urls[0][1])}">中文</a>')
    return f"""<!doctype html>
<html lang="{'zh-CN' if zh else 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(page)}">{alts}
<meta property="og:type" content="article"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(page)}"><meta property="og:image" content="{esc(image)}"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="{root}icons/icon-192.png"><link rel="manifest" href="{root}manifest.webmanifest">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")}</script>
<style>
:root{{--bg:#F4F6F3;--surface:#fff;--ink:#17211E;--muted:#5A6762;--line:#DCE2DD;--accent:#0D6A5A;--a-bg:#E1F0EA}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0F1614;--surface:#162120;--ink:#E7EEEA;--muted:#93A29B;--line:#263431;--accent:#4DC2A6;--a-bg:#17352E;color-scheme:dark}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 'Noto Sans SC','PingFang SC','Microsoft YaHei',system-ui,sans-serif;padding:0 16px 48px}}
.wrap{{max-width:760px;margin:0 auto}}header{{display:flex;justify-content:space-between;align-items:center;padding:18px 0 4px;font-size:14px}}
a{{color:var(--accent)}}header a{{text-decoration:none}}.brand{{font-weight:700;color:var(--ink)}}
h1{{font:700 clamp(26px,5vw,36px)/1.25 'Noto Serif SC','Songti SC',serif;margin:18px 0 8px}}h2{{font-size:20px;margin:30px 0 10px}}
.lead{{color:var(--muted);margin:0}}
.item{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:12px}}.item h3{{margin:0 0 6px;font-size:17px}}.item p{{margin:4px 0}}
.when{{font-weight:600}}.who,.where{{color:var(--muted);font-size:14px}}.tag{{font-size:12px;background:var(--a-bg);color:var(--accent);border-radius:999px;padding:1px 8px;margin-left:6px;vertical-align:2px}}
.cta{{display:inline-block;margin-top:24px;padding:10px 16px;background:var(--accent);color:#fff;border-radius:10px;text-decoration:none;font-weight:600}}
footer{{margin-top:32px;padding-top:14px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}}
</style></head><body><div class="wrap">
<header><a class="brand" href="{esc(city_page)}">← {"周末不无聊" if zh else "No Boring Weekends"} · {esc(cname)}</a>{other}</header>
<h1>{esc(h1)}</h1>
<p class="lead">{esc(desc)}</p>
{sections}
<a class="cta" href="{esc(city_page)}">{"看" + esc(cname) + "这周的活动 →" if zh else "See this week's events in " + esc(cname) + " →"}</a>
<footer>{"日期、时间和票价可能调整，出发前请以官网为准。" if zh else "Dates, hours and prices can change; check the official site before you go."} {"更新于" if zh else "Updated"} {data["updated"]}.</footer>
</div></body></html>
"""
