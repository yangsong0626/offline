#!/usr/bin/env python3
"""给搜索引擎和 AI 搜索生成纯 HTML 页面（主站内容由 JavaScript 渲染，很多 AI 爬虫看不到）。

每个城市生成中、英两个固定网址的「本周末活动」页，每周随 events.json 刷新：
  docs/zh/<city>/index.html   docs/en/<city>/index.html
另外生成两个语言的城市目录页、sitemap.xml、robots.txt、llms.txt，并往 docs/index.html 注入可抓取的城市链接。
只用 Python 标准库（需要 3.9+ 的 zoneinfo）。

用法：python scripts/build_seo.py            # 读 docs/events.json，写入 docs/
网站地址：环境变量 SITE_URL，未设置时读 site.json 的 "url"。
"""
import html, json, os, re, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
cfg = json.load(open(os.path.join(ROOT, "site.json"), encoding="utf-8"))
SITE = (os.environ.get("SITE_URL") or cfg["url"]).rstrip("/")
NAME = {"zh": "周末不无聊", "en": "No Boring Weekends"}
D = json.load(open(os.path.join(DOCS, "events.json"), encoding="utf-8"))
WK = D["weekend"]
UPD = D.get("updated", WK["start"])
CITIES = D["cities"]
LANG_TAG = {"zh": "zh-CN", "en": "en"}

AUD = {"family": {"zh": "亲子", "en": "Family"}, "adult": {"zh": "大人", "en": "Adults"}, "all": {"zh": "大人小孩都适合", "en": "All ages"}}
WD = {"zh": "一二三四五六日", "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def d(s):
    return datetime.strptime(s, "%Y-%m-%d")


def date_label(s, lang):
    x = d(s)
    if lang == "zh":
        return f"{x.month}月{x.day}日（周{WD['zh'][x.weekday()]}）"
    return f"{WD['en'][x.weekday()]}, {MON[x.month - 1]} {x.day}"


def range_label(lang):
    a, b = d(WK["start"]), d(WK["end"])
    if lang == "zh":
        return f"{a.month}月{a.day}日–{b.month}月{b.day}日" if a.month != b.month else f"{a.month}月{a.day}–{b.day}日"
    return f"{MON[a.month - 1]} {a.day}–{b.day}" if a.month == b.month else f"{MON[a.month - 1]} {a.day} – {MON[b.month - 1]} {b.day}"


def time_label(ev, lang):
    if not ev.get("start"):
        return "时间见官网" if lang == "zh" else "See website for times"
    def one(t):
        h, m = map(int, t.split(":")[:2])
        if lang == "en" and h >= 24:
            return "midnight" if (h, m) == (24, 0) else t
        return f"{h:02d}:{m:02d}" if lang == "zh" else f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    return one(ev["start"]) + (f"–{one(ev['end'])}" if ev.get("end") else "")


def iso(ev, which, tz):
    t = ev.get(which)
    if not t:
        return ev["date"]  # 无固定时间：只给日期
    try:
        h, m = map(int, t.split(":")[:2])
    except ValueError:
        return ev["date"]
    x = d(ev["date"]).replace(tzinfo=ZoneInfo(tz)) + timedelta(hours=h, minutes=m)  # 24:00、跨夜都能处理
    if which == "end" and ev.get("start") and x.isoformat() <= iso(ev, "start", tz):
        x += timedelta(days=1)
    return x.isoformat()


def city_name(c, lang):
    return c["zh"] if lang == "zh" else c["en"]


def url_for(lang, cid=None):
    return f"{SITE}/{lang}/" + (f"{cid}/" if cid else "")


def T(ev, k, lang):
    return ev.get(f"{k}_{lang}") or ev.get(f"{k}_zh" if lang == "en" else f"{k}_en") or ""


def event_ld(ev, c, lang):
    o = {"@type": "Event", "name": T(ev, "title", lang), "startDate": iso(ev, "start", c["tz"]),
         "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
         "eventStatus": "https://schema.org/EventScheduled",
         "location": {"@type": "Place", "name": ev.get("venue") or ev.get("area"), "address": ev.get("address") or ev.get("area")},
         "description": T(ev, "desc", lang)[:500], "url": ev.get("url"), "isAccessibleForFree": bool(ev.get("free")),
         "inLanguage": LANG_TAG[lang]}
    if ev.get("end") and ev.get("start"):
        o["endDate"] = iso(ev, "end", c["tz"])
    if ev.get("free"):
        o["offers"] = {"@type": "Offer", "price": 0, "priceCurrency": "CAD" if c["tz"].startswith("America/Toronto") or c["tz"].startswith("America/Vancouver") else "USD",
                       "url": ev.get("url"), "availability": "https://schema.org/InStock"}
    return {k: v for k, v in o.items() if v not in (None, "")}


CSS = """:root{--bg:#F4F6F3;--surface:#fff;--ink:#17211E;--muted:#5A6762;--line:#DCE2DD;--accent:#0D6A5A;--chip:#EBEFEA;--a-bg:#E1F0EA}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0F1614;--surface:#18211E;--ink:#E6ECE9;--muted:#9AA8A2;--line:#2A3632;--accent:#5CC4AE;--chip:#222D29;--a-bg:#16302A;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 "Noto Sans SC","PingFang SC","DM Sans",system-ui,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:20px 16px 56px}a{color:var(--accent)}
nav.top{display:flex;justify-content:space-between;gap:12px;font-size:14px;color:var(--muted);margin-bottom:8px;flex-wrap:wrap}
h1{font-size:26px;line-height:1.3;margin:8px 0 10px;text-wrap:balance}.lead{color:var(--muted);margin:0 0 16px}
.cta{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;padding:8px 14px;border-radius:8px;font-weight:600;font-size:15px}
article{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
article h2{font-size:18px;margin:0 0 6px;line-height:1.4}.meta{font-size:14px;color:var(--muted);margin:0 0 8px}
.chips span{display:inline-block;font-size:12px;background:var(--chip);border-radius:20px;padding:1px 9px;margin:0 4px 4px 0}
.chips span.a{background:var(--a-bg);color:var(--accent);font-weight:600}article p.desc{white-space:pre-line;margin:6px 0}
ul.cities{columns:2 200px;padding-left:20px}footer{margin-top:32px;font-size:13px;color:var(--muted);border-top:1px solid var(--line);padding-top:12px}"""


def shell(lang, title, desc, url, alt, body, ld):
    other = "en" if lang == "zh" else "zh"
    links = "".join(f'<link rel="alternate" hreflang="{LANG_TAG[l]}" href="{e(u)}">' for l, u in alt.items())
    links += f'<link rel="alternate" hreflang="x-default" href="{e(alt["zh"])}">'
    return f"""<!doctype html>
<html lang="{LANG_TAG[lang]}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc[:300])}">
<link rel="canonical" href="{e(url)}">{links}
<meta property="og:type" content="website"><meta property="og:site_name" content="{e(NAME[lang])}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc[:300])}"><meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{SITE}/icons/icon-512.png"><meta name="twitter:card" content="summary">
<link rel="icon" type="image/png" sizes="192x192" href="{SITE}/icons/icon-192.png">
<link rel="stylesheet" href="{SITE}/seo.css">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")}</script>
</head><body><div class="wrap">
{body}
<footer>{"每周五更新。活动信息以主办方官网为准，出发前请再确认时间和是否需要报名。" if lang == "zh" else "Updated every Friday. Details come from organizers; please confirm times and sign-up on their website before you go."}
 · <a href="{url_for(lang)}">{"全部城市" if lang == "zh" else "All cities"}</a> · <a href="{alt[other]}">{"English" if lang == "zh" else "中文"}</a></footer>
</div></body></html>
"""


def city_page(cid, c, lang):
    url = url_for(lang, cid)
    alt = {l: url_for(l, cid) for l in ("zh", "en")}
    cn, rng, evs = city_name(c, lang), range_label(lang), c["events"]
    fam = sum(1 for x in evs if x.get("audience") in ("family", "all"))
    free = sum(1 for x in evs if x.get("free"))
    asian = [x for x in evs if x.get("tier") == "A"]
    if lang == "zh":
        title = f"{cn}周末亲子活动和好去处（{rng}）· 免费活动、华人社区活动 | {NAME['zh']}"
        h1 = f"{cn}本周末去哪儿玩（{rng}）"
        lead = (f"{rng}{cn}精选 {len(evs)} 个周末活动，其中亲子可去 {fam} 个、免费 {free} 个"
                + (f"，华人 / 亚裔社区活动 {len(asian)} 个排在最前" if asian else "") + f"。每个活动附时间、地址、费用、适合年龄和官网链接，{UPD} 更新。")
    else:
        title = f"Things to Do This Weekend in {cn} with Kids ({rng}) · Free Family Events | {NAME['en']}"
        h1 = f"{cn} Weekend Events ({rng})"
        lead = (f"{len(evs)} hand-picked weekend events in {cn} for {rng}: {fam} family-friendly, {free} free"
                + (f", with {len(asian)} Chinese / Asian community events listed first" if asian else "")
                + f". Each lists time, address, cost, ages and the official link. Updated {UPD}.")
    app = f"{SITE}/?city={cid}&lang={lang}"
    b = [f'<nav class="top"><a href="{url_for(lang)}">{e(NAME[lang])}</a><a href="{alt["en" if lang == "zh" else "zh"]}" hreflang="{"en" if lang == "zh" else "zh-CN"}">{"English" if lang == "zh" else "中文"}</a></nav>',
         f"<h1>{e(h1)}</h1>", f'<p class="lead">{e(lead)}</p>',
         f'<p><a class="cta" href="{e(app)}">{"打开完整版：按距离筛选、一键加日历" if lang == "zh" else "Open the app: filter and add to calendar"}</a></p>']
    for x in evs:
        chips = [f'<span class="a">{"华人社区" if lang == "zh" else "Chinese / Asian community"}</span>'] if x.get("tier") == "A" else []
        chips += [f"<span>{e(AUD.get(x.get('audience'), {}).get(lang, ''))}</span>",
                  f"<span>{e(T(x, 'cost', lang))}</span>", f"<span>{e(T(x, 'ages', lang))}</span>",
                  f"<span>{('室内' if x.get('indoor') else '户外') if lang == 'zh' else ('Indoor' if x.get('indoor') else 'Outdoor')}</span>"]
        if x.get("signup"):
            chips.append(f"<span>{'需报名' if lang == 'zh' else 'Sign-up required'}</span>")
        b.append(f'<article id="{e(x["id"])}"><h2>{e(T(x, "title", lang))}</h2>'
                 f'<p class="meta">{e(date_label(x["date"], lang))} · {e(time_label(x, lang))}<br>{e(x.get("venue"))} · {e(x.get("address") or x.get("area"))}</p>'
                 f'<div class="chips">{"".join(c_ for c_ in chips if "<span></span>" not in c_)}</div>'
                 f'<p class="desc">{e(T(x, "desc", lang))}</p>'
                 f'<a href="{e(x.get("url"))}" rel="nofollow noopener">{"官网 / 报名" if lang == "zh" else "Official page"}</a></article>')
    others = [k for k in CITIES if k != cid]
    b.append(f'<h2 style="font-size:17px;margin-top:28px">{"其他城市" if lang == "zh" else "Other cities"}</h2><ul class="cities">'
             + "".join(f'<li><a href="{url_for(lang, k)}">{e(city_name(CITIES[k], lang))}</a></li>' for k in others) + "</ul>")
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": url, "url": url, "name": title, "description": lead, "inLanguage": LANG_TAG[lang],
         "dateModified": UPD, "isPartOf": {"@id": SITE + "/#website"},
         "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
             {"@type": "ListItem", "position": 1, "name": NAME[lang], "item": url_for(lang)},
             {"@type": "ListItem", "position": 2, "name": cn, "item": url}]},
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(evs), "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "item": event_ld(x, c, lang)} for i, x in enumerate(evs)]}}]}
    return url, shell(lang, title, lead, url, alt, "\n".join(b), ld)


def hub_page(lang):
    url = url_for(lang)
    alt = {l: url_for(l) for l in ("zh", "en")}
    n = sum(len(c["events"]) for c in CITIES.values())
    if lang == "zh":
        title = f"北美华人周末活动指南（{range_label('zh')}）：{len(CITIES)} 个城市亲子活动 | {NAME['zh']}"
        lead = f"{range_label('zh')}，{len(CITIES)} 个北美城市共 {n} 个周末活动，亲子和大人活动都有，华人与亚裔社区活动优先，每周五更新。"
    else:
        title = f"Weekend Family Events in {len(CITIES)} North American Cities ({range_label('en')}) | {NAME['en']}"
        lead = f"{n} hand-picked weekend events across {len(CITIES)} North American cities for {range_label('en')}, with Chinese and Asian community events first. Updated every Friday."
    b = [f'<nav class="top"><span>{e(NAME[lang])}</span><a href="{alt["en" if lang == "zh" else "zh"]}">{"English" if lang == "zh" else "中文"}</a></nav>',
         f"<h1>{e(title.split(' | ')[0])}</h1>", f'<p class="lead">{e(lead)}</p>',
         f'<p><a class="cta" href="{SITE}/?lang={lang}">{"打开完整版" if lang == "zh" else "Open the app"}</a></p><ul class="cities">'
         + "".join(f'<li><a href="{url_for(lang, k)}">{e(city_name(c, lang))}</a>（{len(c["events"])}）</li>' for k, c in CITIES.items()) + "</ul>"]
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "@id": url, "url": url, "name": title,
          "inLanguage": LANG_TAG[lang], "dateModified": UPD, "isPartOf": {"@id": SITE + "/#website"}}
    return url, shell(lang, title, lead, url, alt, "\n".join(b), ld)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text:
        return
    open(path, "w", encoding="utf-8").write(text)


write(os.path.join(DOCS, "seo.css"), CSS + "\n")
urls = [(SITE + "/", UPD)]
for lang in ("zh", "en"):
    u, p = hub_page(lang)
    write(os.path.join(DOCS, lang, "index.html"), p)
    urls.append((u, UPD))
    keep = set()
    for cid, c in CITIES.items():
        u, p = city_page(cid, c, lang)
        write(os.path.join(DOCS, lang, cid, "index.html"), p)
        urls.append((u, UPD))
        keep.add(cid)
    for old in os.listdir(os.path.join(DOCS, lang)):  # 去掉已下线的城市
        pth = os.path.join(DOCS, lang, old)
        if os.path.isdir(pth) and old not in keep:
            for f in os.listdir(pth):
                os.remove(os.path.join(pth, f))
            os.rmdir(pth)

# sitemap 带 hreflang
alt_of = lambda u: u.replace(f"{SITE}/zh/", f"{SITE}/en/") if f"{SITE}/zh/" in u else u.replace(f"{SITE}/en/", f"{SITE}/zh/")
sm = ['<?xml version="1.0" encoding="UTF-8"?>',
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
for u, m in urls:
    extra = ""
    if "/zh/" in u or "/en/" in u:
        zh, en = (u, alt_of(u)) if "/zh/" in u else (alt_of(u), u)
        extra = (f'<xhtml:link rel="alternate" hreflang="zh-CN" href="{e(zh)}"/>'
                 f'<xhtml:link rel="alternate" hreflang="en" href="{e(en)}"/>')
    sm.append(f"<url><loc>{e(u)}</loc><lastmod>{e(m)}</lastmod>{extra}</url>")
sm.append("</urlset>")
write(os.path.join(DOCS, "sitemap.xml"), "\n".join(sm) + "\n")

write(os.path.join(DOCS, "robots.txt"), f"""# 欢迎搜索引擎和 AI 搜索抓取 / Search engines and AI assistants are welcome
User-agent: *
Allow: /
Disallow: /xhs.html

User-agent: OAI-SearchBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: GPTBot
Allow: /
User-agent: Claude-SearchBot
Allow: /
User-agent: Claude-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Perplexity-User
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: Applebot-Extended
Allow: /

Sitemap: {SITE}/sitemap.xml
""")

write(os.path.join(DOCS, "llms.txt"), f"""# {NAME['zh']} {NAME['en']}

> 北美华人周末活动指南：{len(CITIES)} 个城市的亲子和大人周末活动，华人与亚裔社区活动优先，中英双语，每周五更新（本期 {range_label('zh')}，更新于 {UPD}）。
> Weekend events for families in {len(CITIES)} North American cities, Chinese/Asian community events first, bilingual, updated every Friday.

每个城市有固定网址的「本周末」页面，内容每周替换。活动信息以主办方官网为准。

## 城市页（中文）
""" + "".join(f"- [{c['zh']}本周末活动]({url_for('zh', k)})\n" for k, c in CITIES.items()) + """
## City pages (English)
""" + "".join(f"- [{c['en']} weekend events]({url_for('en', k)})\n" for k, c in CITIES.items()))

# 主页：注入 canonical / hreflang / 结构化数据和可抓取的城市链接
idx = os.path.join(DOCS, "index.html")
h = open(idx, encoding="utf-8").read()
head = (f'<link rel="canonical" href="{SITE}/">'
        f'<link rel="alternate" hreflang="zh-CN" href="{url_for("zh")}"><link rel="alternate" hreflang="en" href="{url_for("en")}">'
        f'<link rel="alternate" hreflang="x-default" href="{SITE}/">'
        f'<meta property="og:type" content="website"><meta property="og:site_name" content="{NAME["zh"]}">'
        f'<meta property="og:title" content="{NAME["zh"]} No Boring Weekends：北美华人周末活动指南">'
        f'<meta property="og:description" content="{len(CITIES)} 个北美城市的亲子和大人周末活动，华人与亚裔社区活动优先，每周五更新。">'
        f'<meta property="og:url" content="{SITE}/"><meta property="og:image" content="{SITE}/icons/icon-512.png">'
        '<script type="application/ld+json">' + json.dumps(
            {"@context": "https://schema.org", "@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/",
             "name": NAME["zh"], "alternateName": NAME["en"], "inLanguage": ["zh-CN", "en"],
             "description": f"Weekend events for families in {len(CITIES)} North American cities, Chinese and Asian community events first, updated every Friday."},
            ensure_ascii=False) + "</script>")
h = re.sub(r"<!--SEO-HEAD-->.*?<!--/SEO-HEAD-->", "", h, flags=re.S)
h = h.replace("</head>", f"<!--SEO-HEAD-->{head}<!--/SEO-HEAD-->\n</head>", 1)
nav = ('<nav class="seo-cities" aria-label="城市 Cities">'
       + " · ".join(f'<a href="zh/{k}/">{e(c["zh"])}</a>' for k, c in CITIES.items()) + "<br>"
       + " · ".join(f'<a href="en/{k}/">{e(c["en"])}</a>' for k, c in CITIES.items()) + "</nav>")
h = re.sub(r"<!--SEO-NAV-->.*?<!--/SEO-NAV-->", "", h, flags=re.S)
h = h.replace('<footer class="foot" id="foot"></footer>', f'<footer class="foot" id="foot"></footer>\n  <!--SEO-NAV-->{nav}<!--/SEO-NAV-->', 1)
assert "<!--SEO-NAV-->" in h, "footer marker not found in docs/index.html"
open(idx, "w", encoding="utf-8").write(h)

print(f"seo: {len(CITIES)} cities × 2 languages, {len(urls)} urls, base {SITE}", file=sys.stderr)
