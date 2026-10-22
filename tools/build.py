#!/usr/bin/env python3
"""Build static extras from docs/events.json (stdlib only; runs as the Cloudflare Pages build command).

Writes, under docs/:
  <city>/index.html     Chinese city page   } own title/description/canonical/hreflang/Open Graph,
  en/<city>/index.html  English city page   } prerendered event cards, schema.org Event JSON-LD
  en/index.html         English home page
  cal/<city>.ics        subscribable calendar feed per city
  sitemap.xml, robots.txt, llms.txt
and refreshes the marked SEO block and city links in docs/index.html (the Chinese home page).

Site URL: tools/site.json "url", or the SITE_URL environment variable.
"""
import html, json, os, re, sys
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deals as D  # noqa: E402  (tools/deals.py)
DOCS = os.path.join(ROOT, "docs")
SITE = json.load(open(os.path.join(ROOT, "tools", "site.json"), encoding="utf-8"))
URL = (os.environ.get("SITE_URL") or SITE["url"]).rstrip("/")
CURRENCY = {"tor": "CAD", "van": "CAD"}
AI_BOTS = ["OAI-SearchBot", "ChatGPT-User", "GPTBot", "Claude-SearchBot", "Claude-User", "ClaudeBot",
           "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended"]
L = {
 "zh": {"wd": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"], "tbd": "时间见官网", "free": "免费", "ages": "适合",
        "site": "活动官网", "soon": "这个城市本周的活动还在整理中。", "locale": "zh_CN", "lang": "zh-CN",
        "name": SITE["name_zh"], "links": "{c}周末活动", "weekend": "{c} · {r} 周末"},
 "en": {"wd": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "tbd": "See site", "free": "Free", "ages": "Ages",
        "site": "Event site", "soon": "Events for this city are still being compiled.", "locale": "en_US", "lang": "en",
        "name": SITE["name_en"], "links": "{c} weekend events", "weekend": "{c} · Weekend of {r}"},
}
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def esc(s): return html.escape(str(s or ""), quote=True)
def ymd(d): return tuple(map(int, d.split("-")))
def md(d): y, m, dd = ymd(d); return f"{m}/{dd}"
def weekday(d, lang): return L[lang]["wd"][datetime.strptime(d, "%Y-%m-%d").weekday()]
def sort_key(e, lang="zh"):
    """Chinese pages put Chinese/Asian community events first; English pages are plain date order."""
    when = (e["date"], e.get("start") or "99")  # time TBD sorts last within its day
    return (e["tier"], *when) if lang == "zh" else when
def tx(e, field, lang): return e.get(f"{field}_{lang}") or e.get(f"{field}_zh") or ""
def cname(c, lang): return c["zh"] if lang == "zh" else c["en"]

def date_range(wk, lang):
    (_, m1, d1), (_, m2, d2) = ymd(wk["start"]), ymd(wk["end"])
    if lang == "zh": return f"{m1}/{d1}–{m2}/{d2}"
    return f"{MON[m1-1]} {d1}–{d2}" if m1 == m2 else f"{MON[m1-1]} {d1}–{MON[m2-1]} {d2}"

def page_url(cid, lang):
    return URL + "/" + ("en/" if lang == "en" else "") + (f"{cid}/" if cid else "")

def local_dt(date, time, tz):
    extra = timedelta(0)
    if time.startswith("24:"):  # "24:00" means midnight at the end of the day
        time, extra = "00:" + time[3:], timedelta(days=1)
    dt = datetime.strptime(date + " " + time, "%Y-%m-%d %H:%M") + extra
    if ZoneInfo:
        try: return dt.replace(tzinfo=ZoneInfo(tz))
        except Exception: pass
    return None

def iso(date, time, tz):
    if not time: return date
    dt = local_dt(date, time, tz)
    return dt.isoformat() if dt else date + "T" + time

def seo_block(lang, title, desc, cid, image, ld):
    canon = page_url(cid, lang)
    alts = "".join(f'<link rel="alternate" hreflang="{h}" href="{esc(u)}">\n' for h, u in
                   (("zh-CN", page_url(cid, "zh")), ("en", page_url(cid, "en")), ("x-default", page_url(cid, "zh"))))
    return (f'<!--seo-->\n<title>{esc(title)}</title>\n<meta name="description" content="{esc(desc)}">\n'
            f'<link rel="canonical" href="{esc(canon)}">\n{alts}'
            f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="{esc(L[lang]["name"])}">\n'
            f'<meta property="og:title" content="{esc(title)}">\n<meta property="og:description" content="{esc(desc)}">\n'
            f'<meta property="og:url" content="{esc(canon)}">\n<meta property="og:image" content="{esc(image)}">\n'
            f'<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
            f'<meta property="og:locale" content="{L[lang]["locale"]}">\n<meta name="twitter:card" content="summary_large_image">\n'
            '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
            "<!--/seo-->")

def city_links(cities, lang):
    pre = "en/" if lang == "en" else ""
    return ('<!--citylinks--><nav class="citylinks" aria-label="Cities">'
            + "".join(f'<a href="{pre}{cid}/">{esc(L[lang]["links"].format(c=cname(c, lang)))}</a>' for cid, c in cities.items())
            + "</nav><!--/citylinks-->")

def card_html(e, lang):
    t = esc(e.get("start") or L[lang]["tbd"]) + (("<br>" + esc(e["end"])) if e.get("end") else "")
    cost = L[lang]["free"] if e.get("free") else tx(e, "cost", lang)
    return (f'<article class="card" id="e-{esc(e["id"])}"><div class="when"><span class="d">{md(e["date"])}</span>'
            f'<span class="w">{weekday(e["date"], lang)}</span><span class="t">{t}</span></div><div class="body">'
            f'<h3>{esc(tx(e, "title", lang))}</h3><p class="where">{esc(e["venue"])} · {esc(e["address"])}</p>'
            f'<div class="meta"><span>{esc(cost)}</span><span>{L[lang]["ages"]} {esc(tx(e, "ages", lang))}</span></div>'
            f'<p class="desc">{esc(tx(e, "desc", lang))}</p>'
            f'<div class="actions"><a class="link" href="{esc(e["url"])}" rel="noopener">{L[lang]["site"]} ↗</a></div></div></article>')

def event_ld(e, cid, tz, page, image, lang):
    ld = {"@type": "Event", "name": tx(e, "title", lang), "startDate": iso(e["date"], e.get("start"), tz),
          "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
          "eventStatus": "https://schema.org/EventScheduled",
          "location": {"@type": "Place", "name": e["venue"], "address": e["address"]},
          "description": re.sub(r"\s*\n\s*", " ", tx(e, "desc", lang)),
          "image": [image], "url": f"{page}#e-{e['id']}", "isAccessibleForFree": bool(e.get("free")),
          "inLanguage": L[lang]["lang"], "sameAs": e["url"]}
    if e.get("start") and e.get("end"):
        ld["endDate"] = iso(e["date"], e["end"], tz)
    if e.get("free"):
        ld["offers"] = {"@type": "Offer", "price": 0, "priceCurrency": CURRENCY.get(cid, "USD"),
                        "availability": "https://schema.org/InStock", "url": e["url"]}
    return ld

def website_ld():
    return {"@type": "WebSite", "@id": URL + "/#website", "url": URL + "/", "name": SITE["name_zh"],
            "alternateName": SITE["name_en"], "inLanguage": ["zh-CN", "en"]}

def fold(line):
    out, b = [], line.encode("utf-8")
    while len(b) > 75:
        cut = 75
        while cut > 0 and (b[cut] & 0xC0) == 0x80: cut -= 1  # do not split a UTF-8 sequence
        out.append(b[:cut].decode("utf-8")); b = b" " + b[cut:]
    out.append(b.decode("utf-8")); return "\r\n".join(out)

def ics_text(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def ics(cid, city, events, stamp):
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//No Boring Weekends//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
           "X-WR-CALNAME:" + ics_text(f'{SITE["name_zh"]} · {city["zh"]}'), "X-WR-TIMEZONE:" + city["tz"],
           "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    utc = lambda d: d.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    for e in events:
        out += ["BEGIN:VEVENT", f"UID:{e['id']}-{e['date']}@noboringweekends", "DTSTAMP:" + stamp]
        s = local_dt(e["date"], e["start"], city["tz"]) if e.get("start") else None
        if s:
            en = local_dt(e["date"], e["end"], city["tz"]) if e.get("end") else s + timedelta(hours=2)
            out += ["DTSTART:" + utc(s), "DTEND:" + utc(en)]
        else:
            d = datetime.strptime(e["date"], "%Y-%m-%d")
            out += ["DTSTART;VALUE=DATE:" + d.strftime("%Y%m%d"), "DTEND;VALUE=DATE:" + (d + timedelta(days=1)).strftime("%Y%m%d")]
        cost = "免费" if e.get("free") else e.get("cost_zh", "")
        out += ["SUMMARY:" + ics_text(e["title_zh"]), "LOCATION:" + ics_text(e["venue"] + ", " + e["address"]),
                "DESCRIPTION:" + ics_text(f'{e.get("desc_zh","")}\n费用:{cost}\n{e["url"]}'), "URL:" + e["url"], "END:VEVENT"]
    out.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in out) + "\r\n"

def replace_block(src, name, new):
    pat = re.compile(r"<!--%s-->.*?<!--/%s-->" % (name, name), re.S)
    if not pat.search(src): sys.exit(f"marker <!--{name}--> missing in index.html")
    return pat.sub(lambda m: new, src, count=1)

def city_meta(c, evs, wk, lang):
    rng, name = date_range(wk, lang), cname(c, lang)
    free = sum(1 for e in evs if e.get("free"))
    asian = sum(1 for e in evs if e["tier"] != "C")
    picks = [tx(e, "title", lang) for e in evs[:3]]
    if lang == "zh":
        title = f'{name}周末去哪儿｜{rng} 亲子和大人活动 · {SITE["name_zh"]}'
        desc = (f'{name}这个周末（{rng}）{len(evs)} 个活动' + (f'，其中 {free} 个免费' if free else '')
                + (f'：{"、".join(picks)}等' if picks else '') + '。华人与亚裔社区活动优先，每周更新。')
    else:
        title = f'Things to Do This Weekend in {name} ({rng}) · Family & Grown-Up Events | {SITE["name_en"]}'
        desc = (f'{len(evs)} hand-picked events in {name} for {rng}' + (f', {free} free' if free else '')
                + (f', {asian} Chinese / Asian community events' if asian else '')
                + (f': {"; ".join(picks)}' if picks else '') + '. Updated weekly.')
    return title, desc

def build_page(tpl, lang, cid, data):
    """Turn the home-page template into the page for (lang, city); cid None means a home page."""
    cities, wk = data["cities"], data["weekend"]
    depth = (1 if lang == "en" else 0) + (1 if cid else 0)
    out = replace_block(tpl, "citylinks", city_links(cities, lang))
    if cid:
        c = cities[cid]; evs = sorted(c["events"], key=lambda e: sort_key(e, lang))
        page, image = page_url(cid, lang), f"{URL}/og/{cid}.png"
        title, desc = city_meta(c, evs, wk, lang)
        crumbs = {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": L[lang]["name"], "item": page_url(None, lang)},
            {"@type": "ListItem", "position": 2, "name": cname(c, lang), "item": page}]}
        ld = {"@context": "https://schema.org", "@graph": [website_ld(),
              {"@type": "WebPage", "@id": page, "url": page, "name": title, "description": desc, "inLanguage": L[lang]["lang"],
               "dateModified": data["updated"], "isPartOf": {"@id": URL + "/#website"}, "breadcrumb": crumbs},
              *[event_ld(e, cid, c["tz"], page, image, lang) for e in evs]]}
        out = replace_block(out, "seo", seo_block(lang, title, desc, cid, image, ld))
        out = out.replace('<h2 id="weekend-title"></h2>',
                          f'<h2 id="weekend-title">{esc(L[lang]["weekend"].format(c=cname(c, lang), r=date_range(wk, lang)))}</h2>', 1)
        cards = "".join(card_html(e, lang) for e in evs) or f'<p class="empty">{L[lang]["soon"]}</p>'
        out = out.replace('<div class="list" id="list"></div>', f'<div class="list" id="list">{cards}</div>', 1)
    else:
        if lang == "zh":
            title = "周末不无聊 · 北美华人周末去哪儿"
            desc = f"北美华人周末活动指南：纽约、湾区、洛杉矶、西雅图、多伦多、温哥华等 {len(cities)} 个城市的亲子和大人活动，华人与亚裔社区活动优先，每周更新。"
        else:
            title = "No Boring Weekends · Things to Do This Weekend in North America"
            desc = f"Weekend events for families and grown-ups in {len(cities)} North American cities, from festivals and shows to Chinese and Asian community events. Updated weekly."
        ld = {"@context": "https://schema.org", "@graph": [website_ld(),
              {"@type": "WebPage", "@id": page_url(None, lang), "url": page_url(None, lang), "name": title,
               "inLanguage": L[lang]["lang"], "dateModified": data["updated"], "isPartOf": {"@id": URL + "/#website"}}]}
        out = replace_block(out, "seo", seo_block(lang, title, desc, None, f"{URL}/og/default.png", ld))
    if depth:
        out = out.replace('<meta charset="utf-8">', f'<meta charset="utf-8"><base href="{"../" * depth}">', 1)
    flags = ([f'window.PAGE_CITY="{cid}"'] if cid else []) + ([f'window.PAGE_LANG="{lang}"'] if (cid or lang == "en") else [])
    if flags:
        out = out.replace('<script src="sky.js"></script>', f'<script>{";".join(flags)}</script>\n<script src="sky.js"></script>', 1)
    if lang == "en":
        out = out.replace('<html lang="zh-CN">', '<html lang="en">', 1)
    return out

def write(path, text, newline=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=newline) as f: f.write(text)

def guide_url(cid, lang): return page_url(cid, lang) + "guides/free/"

def llms_txt(data, guides=()):
    cities, wk = data["cities"], data["weekend"]
    out = [f'# {SITE["name_zh"]} {SITE["name_en"]}', "",
           f'> 北美华人周末活动指南：{len(cities)} 个城市的亲子和大人周末活动，华人与亚裔社区活动优先，中英双语，每周更新（本期 {date_range(wk, "zh")}，更新于 {data["updated"]}）。',
           f'> Weekend events for families and grown-ups in {len(cities)} North American cities (festivals, shows, family outings, Chinese/Asian community events), bilingual, updated weekly.', "",
           "每个城市有固定网址的「本周末」页面，内容每周替换；每个城市还有可订阅的日历（.ics）。活动信息以主办方官网为准。",
           "Each city has a fixed weekend page that is replaced weekly, plus a subscribable .ics calendar. Check organizers' sites before going.", ""]
    for lang, head in (("zh", "## 城市页（中文）"), ("en", "## City pages (English)")):
        out.append(head)
        for cid, c in cities.items():
            evs = sorted(c["events"], key=lambda e: sort_key(e, lang))
            label = f'{cname(c, lang)}本周末活动' if lang == "zh" else f'{cname(c, lang)} weekend events'
            tops = "、".join(tx(e, "title", lang) for e in evs[:3]) if lang == "zh" else "; ".join(tx(e, "title", lang) for e in evs[:3])
            out.append(f"- [{label}]({page_url(cid, lang)}): {len(evs)} " + ("个活动，" if lang == "zh" else "events, e.g. ") + tops)
        out.append("")
    if guides:
        out += ["## 免费 / 优惠攻略 Free-day guides", *[f"- [{cities[cid]['zh']}免费博物馆日 & 优惠 / Free museum days in {cities[cid]['en']}]({guide_url(cid, 'zh')})" for cid in guides], ""]
    out += ["## Calendar feeds", *[f"- [{c['en']} (.ics)]({URL}/cal/{cid}.ics)" for cid, c in cities.items()], "",
            "## Data", f"- [events.json]({URL}/events.json): all events with dates, times, venues, prices and official links", ""]
    return "\n".join(out)

def not_found(cities):
    """404 page: send broken paths like /nj/la/atl/ to the last city in them, anything else home."""
    ids = json.dumps(list(cities))
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>周末不无聊</title></head><body style="font-family:system-ui,sans-serif;padding:24px">'
            '<p>页面不存在，正在带你回首页… / Page not found, taking you home…</p><p><a href="/">周末不无聊 · No Boring Weekends</a></p>'
            '<script>(function(){var ids=' + ids + ',seg=location.pathname.split("/").filter(Boolean),en=seg[0]==="en",c=null;'
            'for(var i=seg.length-1;i>=0;i--){if(ids.indexOf(seg[i])>-1){c=seg[i];break}}'
            'location.replace("/"+(en?"en/":"")+(c?c+"/":"")+location.hash)})()</script></body></html>\n')

def main():
    data = json.load(open(os.path.join(DOCS, "events.json"), encoding="utf-8"))
    cities = data["cities"]
    tpl = open(os.path.join(DOCS, "index.html"), encoding="utf-8").read()
    stamp = data["updated"].replace("-", "") + "T000000Z"  # deterministic, so rebuilds without data changes are no-ops

    write(os.path.join(DOCS, "index.html"), build_page(tpl, "zh", None, data))
    tpl = open(os.path.join(DOCS, "index.html"), encoding="utf-8").read()
    write(os.path.join(DOCS, "en", "index.html"), build_page(tpl, "en", None, data))
    urls = [(None)]
    for cid, c in cities.items():
        write(os.path.join(DOCS, cid, "index.html"), build_page(tpl, "zh", cid, data))
        write(os.path.join(DOCS, "en", cid, "index.html"), build_page(tpl, "en", cid, data))
        write(os.path.join(DOCS, "cal", cid + ".ics"), ics(cid, c, sorted(c["events"], key=sort_key), stamp), newline="")
        urls.append(cid)

    # Free / discount guides for cities that have rules in deals.json.
    deals_path = os.path.join(DOCS, "deals.json")
    deals = json.load(open(deals_path, encoding="utf-8")) if os.path.exists(deals_path) else {"deals": [], "updated": data["updated"]}
    deals_updated, guides = deals["updated"], []
    for cid, c in cities.items():
        mine = D.for_city(deals["deals"], cid)
        if not mine: continue
        alts = [("zh-CN", guide_url(cid, "zh")), ("en", guide_url(cid, "en")), ("x-default", guide_url(cid, "zh"))]
        for lang in ("zh", "en"):
            out = D.guide_html(cid, c, mine, lang, data, guide_url, f"{URL}/og/{cid}.png", alts)
            write(os.path.join(DOCS, *(["en"] if lang == "en" else []), cid, "guides", "free", "index.html"), out)
        guides.append(cid)

    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for cid in urls:
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{h}" href="{page_url(cid, l)}"/>'
                       for h, l in (("zh-CN", "zh"), ("en", "en"), ("x-default", "zh")))
        for lang in ("zh", "en"):
            sm.append(f'  <url><loc>{page_url(cid, lang)}</loc><lastmod>{data["updated"]}</lastmod>'
                      f'<changefreq>weekly</changefreq>{alts}</url>')
    for cid in guides:
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{h}" href="{guide_url(cid, l)}"/>'
                       for h, l in (("zh-CN", "zh"), ("en", "en"), ("x-default", "zh")))
        for lang in ("zh", "en"):
            sm.append(f'  <url><loc>{guide_url(cid, lang)}</loc><lastmod>{deals_updated}</lastmod><changefreq>monthly</changefreq>{alts}</url>')
    sm.append("</urlset>")
    write(os.path.join(DOCS, "sitemap.xml"), "\n".join(sm) + "\n")
    robots = ["# Search engines and AI assistants are welcome / 欢迎搜索引擎和 AI 搜索抓取",
              "User-agent: *", "Allow: /", "Disallow: /xhs.html", ""]
    for bot in AI_BOTS: robots += [f"User-agent: {bot}", "Allow: /", "Disallow: /xhs.html", ""]
    robots.append(f"Sitemap: {URL}/sitemap.xml")
    write(os.path.join(DOCS, "robots.txt"), "\n".join(robots) + "\n")
    write(os.path.join(DOCS, "llms.txt"), llms_txt(data, guides))
    write(os.path.join(DOCS, "404.html"), not_found(cities))
    print(f"built {len(cities)} cities x 2 languages, {len(guides)} free-day guides, feeds, sitemap, robots and llms.txt for {URL}")

if __name__ == "__main__":
    main()
