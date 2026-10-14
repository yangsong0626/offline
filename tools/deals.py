"""Recurring free / discount rules (docs/deals.json) and the per-city guide pages built from them.

Rule types (weekday numbers follow JavaScript: 0 = Sunday ... 6 = Saturday):
  weekly             {"days": [5]}            every listed weekday
  monthly            {"nth": 2, "day": 0}     nth given weekday of the month (2nd Sunday); nth may be a list ([1, 2])
  first_full_weekend {}                       first Saturday of the month and the Sunday after it
  always             {}                       any day the eligibility applies
Optional per deal:
  "months": [11, 12, 1]   only in these months (seasonal programs)
  "skip":  ["2026-10-11"] dates the rule would match but the venue cancelled or moved
  "extra": ["2026-10-18"] one-off dates outside the rule
The same logic lives in docs/index.html (dealOn / dealDated / dealAnytime) so the page and the build agree.
"""
import html, json
from datetime import date, timedelta

WD_ZH = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
WD_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
NTH_ZH = {1: "第一", 2: "第二", 3: "第三", 4: "第四", 5: "第五"}
NTH_EN = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}

def esc(s): return html.escape(str(s or ""), quote=True)
def jsday(d): return (d.weekday() + 1) % 7
def nths(r): return r["nth"] if isinstance(r["nth"], list) else [r["nth"]]

def occurs(rule, d):
    t = rule["type"]
    if t == "always": return True
    if t == "weekly": return jsday(d) in rule["days"]
    if t == "monthly": return jsday(d) == rule["day"] and (d.day - 1) // 7 + 1 in nths(rule)
    if t == "first_full_weekend": return (jsday(d) == 6 and d.day <= 7) or (jsday(d) == 0 and 2 <= d.day <= 8)
    raise ValueError("unknown rule type " + t)

def in_season(deal, d): return not deal.get("months") or d.month in deal["months"]

def dated(deal, d):
    """True if a dated (non-always) deal happens on day d."""
    iso = d.isoformat()
    if iso in deal.get("skip", []): return False
    if iso in deal.get("extra", []): return True
    return deal["rule"]["type"] != "always" and in_season(deal, d) and occurs(deal["rule"], d)

def anytime(deal, d): return deal["rule"]["type"] == "always" and in_season(deal, d)

def months_text(ms, lang):
    if not ms: return ""
    return ("(" + "、".join(f"{m}月" for m in ms) + ")") if lang == "zh" else " (" + ", ".join(
        ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m-1] for m in ms) + ")"

def when_text(deal, lang):
    r, t = deal["rule"], deal["rule"]["type"]
    time = (" " + deal["time"]) if deal.get("time") else ""
    if lang == "zh":
        s = {"always": "随时(符合条件即可)", "first_full_weekend": "每月第一个完整周末(周六+周日)"}.get(t)
        if t == "weekly": s = "每" + "、".join(WD_ZH[x] for x in r["days"])
        if t == "monthly": s = "每月" + "、".join(NTH_ZH[n] for n in nths(r)) + "个" + WD_ZH[r["day"]]
        if t == "always" and deal.get("months"): s = "活动月内随时"
    else:
        s = {"always": "Any day you qualify", "first_full_weekend": "First full weekend of every month (Sat + Sun)"}.get(t)
        if t == "weekly": s = "Every " + ", ".join(WD_EN[x] for x in r["days"])
        if t == "monthly": s = " & ".join(NTH_EN[n] for n in nths(r)).capitalize() + f' {WD_EN[r["day"]]} of every month'
        if t == "always" and deal.get("months"): s = "Any day during the program"
    return s + time + months_text(deal.get("months"), lang)

def for_city(deals, cid): return [x for x in deals if cid in x["cities"]]

def upcoming(deals, start, days=35):
    """[(date, [deal, ...])] for dated rules over the next `days` days from start."""
    d0, out = date.fromisoformat(start), []
    for i in range(days):
        d = d0 + timedelta(days=i)
        hits = [x for x in deals if dated(x, d)]
        if hits: out.append((d, hits))
    return out

def guide_html(cid, city, deals, lang, data, url_of, image, alt_urls):
    """Standalone SEO guide page listing a city's free / discount rules plus a 5-week calendar."""
    zh = lang == "zh"
    cname = city["zh"] if zh else city["en"]
    year = data["weekend"]["start"][:4]
    verified = max(x["verified"] for x in deals)
    h1 = f"{cname}免费博物馆日 & 优惠全攻略（{year}）" if zh else f"Free Museum Days & Discounts in {cname} ({year})"
    title = h1 + (" · 周末不无聊" if zh else " · No Boring Weekends")
    desc = (f"{cname}博物馆、动物园、植物园的免费日和随意付费规则：每周固定、每月固定、居民和图书馆卡福利，以及接下来 5 周的免费日历。最后核实 {verified}。" if zh
            else f"Free days and pay-what-you-wish rules for museums, zoos and gardens in {cname}: weekly, monthly, resident and library-card perks, plus a 5-week calendar. Last verified {verified}.")
    page = url_of(cid, lang)
    groups = [("weekly", "每周固定" if zh else "Every week"), ("monthly", "每月固定" if zh else "Every month"),
              ("first_full_weekend", "持卡福利" if zh else "Card perks"), ("always", "随时可用(居民 / 学生 / 借书证)" if zh else "Any day (residents, students, library cards)")]
    t = lambda x, f: x.get(f"{f}_{lang}") or x.get(f"{f}_zh") or ""
    def item(x):
        book = (' <span class="tag">需预约</span>' if zh else ' <span class="tag">Reserve</span>') if x.get("book") else ""
        where = f'<p class="where">{esc(x["venue"])}' + (f' · {esc(x["address"])}' if x.get("address") else "") + "</p>"
        return (f'<article class="item"><h3>{esc(t(x, "title"))}{book}</h3><p class="when">🗓 {esc(when_text(x, lang))}</p>'
                f'<p class="who">👤 {esc(t(x, "who"))}</p>{where}<p>{esc(t(x, "desc"))}</p>'
                f'<p><a href="{esc(x["url"])}" target="_blank" rel="noopener">{"官网 / 详情" if zh else "Official info"} ↗</a></p></article>')
    sections = ""
    for kind, head in groups:
        xs = [x for x in deals if x["rule"]["type"] == kind]
        if xs: sections += f"<h2>{head}</h2>" + "".join(item(x) for x in xs)
    cal_rows = ""
    for d, hits in upcoming(deals, data["weekend"]["start"]):
        wd = (WD_ZH if zh else WD_EN)[jsday(d)]
        weekend = " we" if jsday(d) in (0, 6) else ""
        cal_rows += (f'<li class="row{weekend}"><span class="d">{d.month}/{d.day} {wd}</span><span>'
                     + "、".join(esc(t(x, "title")) for x in hits) + "</span></li>")
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "Article", "@id": page + "#article", "headline": title, "description": desc, "inLanguage": "zh-CN" if zh else "en",
         "dateModified": verified, "image": [image], "mainEntityOfPage": page,
         "author": {"@type": "Organization", "name": "周末不无聊 No Boring Weekends"}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "周末不无聊" if zh else "No Boring Weekends", "item": url_of(None, lang)},
            {"@type": "ListItem", "position": 2, "name": cname, "item": url_of(cid, lang)[: -len("guides/free/")]},
            {"@type": "ListItem", "position": 3, "name": "免费 / 优惠" if zh else "Free days", "item": page}]}]}
    root = "../" * (3 + (0 if zh else 1))
    city_page = url_of(cid, lang)[: -len("guides/free/")]
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
.lead{{color:var(--muted);margin:0}}.cal{{list-style:none;padding:0;margin:0;background:var(--surface);border:1px solid var(--line);border-radius:14px}}
.row{{display:flex;gap:14px;padding:9px 14px;border-top:1px solid var(--line)}}.row:first-child{{border-top:0}}.row .d{{flex:none;width:92px;color:var(--muted);font-variant-numeric:tabular-nums}}.row.we .d{{color:var(--accent);font-weight:600}}
.item{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:12px}}.item h3{{margin:0 0 6px;font-size:17px}}.item p{{margin:4px 0}}
.when{{font-weight:600}}.who,.where{{color:var(--muted);font-size:14px}}.tag{{font-size:12px;background:var(--a-bg);color:var(--accent);border-radius:999px;padding:1px 8px;margin-left:6px;vertical-align:2px}}
.cta{{display:inline-block;margin-top:24px;padding:10px 16px;background:var(--accent);color:#fff;border-radius:10px;text-decoration:none;font-weight:600}}
footer{{margin-top:32px;padding-top:14px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}}
</style></head><body><div class="wrap">
<header><a class="brand" href="{esc(city_page)}">← {"周末不无聊" if zh else "No Boring Weekends"} · {esc(cname)}</a>{other}</header>
<h1>{esc(h1)}</h1>
<p class="lead">{esc(desc)}</p>
<h2>{"接下来 5 周的免费日历" if zh else "Free days in the next 5 weeks"}</h2>
<ul class="cal">{cal_rows}</ul>
{sections}
<a class="cta" href="{esc(city_page)}">{"看" + esc(cname) + "这个周末的活动 →" if zh else "See this weekend's events in " + esc(cname) + " →"}</a>
<footer>{"规则可能随时调整，出发前请以官网为准。" if zh else "Rules can change; check the official site before you go."} {"最后核实" if zh else "Last verified"} {verified}.</footer>
</div></body></html>
"""
