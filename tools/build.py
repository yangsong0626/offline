#!/usr/bin/env python3
"""Build static extras from docs/events.json (stdlib only; runs as the Cloudflare Pages build command).

Writes, under docs/:
  <city>/index.html  per-city page: own title/description/canonical/Open Graph tags,
                     prerendered event cards and schema.org Event JSON-LD
  cal/<city>.ics     subscribable calendar feed per city
  sitemap.xml, robots.txt
and refreshes the marked SEO block and city links in docs/index.html.

Site URL: tools/site.json "url", or the SITE_URL environment variable.
"""
import html, json, os, re, sys
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
SITE = json.load(open(os.path.join(ROOT, "tools", "site.json"), encoding="utf-8"))
URL = (os.environ.get("SITE_URL") or SITE["url"]).rstrip("/")
WD = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
CURRENCY = {"tor": "CAD", "van": "CAD"}

def esc(s): return html.escape(str(s or ""), quote=True)
def md(d): y, m, dd = map(int, d.split("-")); return f"{m}/{dd}"
def weekday(d): return WD[datetime.strptime(d, "%Y-%m-%d").weekday()]
def sort_key(e): return (e["tier"], e["date"], e.get("start") or "")

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

def seo_block(title, desc, canonical, image, extra=""):
    return (f'<!--seo-->\n<title>{esc(title)}</title>\n'
            f'<meta name="description" content="{esc(desc)}">\n'
            f'<link rel="canonical" href="{esc(canonical)}">\n'
            f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="{esc(SITE["name_zh"])}">\n'
            f'<meta property="og:title" content="{esc(title)}">\n<meta property="og:description" content="{esc(desc)}">\n'
            f'<meta property="og:url" content="{esc(canonical)}">\n<meta property="og:image" content="{esc(image)}">\n'
            f'<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
            f'<meta property="og:locale" content="zh_CN">\n<meta name="twitter:card" content="summary_large_image">\n'
            f'{extra}<!--/seo-->')

def city_links(cities):
    return ('<!--citylinks--><nav class="citylinks" aria-label="Cities">'
            + "".join(f'<a href="{cid}/">{esc(c["zh"])}周末活动</a>' for cid, c in cities.items())
            + "</nav><!--/citylinks-->")

def card_html(e):
    t = (e.get("start") or "时间见官网") + (("<br>" + esc(e["end"])) if e.get("end") else "")
    cost = "免费" if e.get("free") else e.get("cost_zh", "")
    return (f'<article class="card" id="e-{esc(e["id"])}"><div class="when"><span class="d">{md(e["date"])}</span>'
            f'<span class="w">{weekday(e["date"])}</span><span class="t">{t}</span></div><div class="body">'
            f'<h3>{esc(e["title_zh"])}</h3><p class="where">{esc(e["venue"])} · {esc(e["address"])}</p>'
            f'<div class="meta"><span>{esc(cost)}</span><span>适合 {esc(e.get("ages_zh"))}</span></div>'
            f'<p class="desc">{esc(e.get("desc_zh"))}</p>'
            f'<div class="actions"><a class="link" href="{esc(e["url"])}" rel="noopener">活动官网 ↗</a></div></div></article>')

def event_ld(e, cid, tz, page, image):
    ld = {"@type": "Event", "name": e["title_zh"], "startDate": iso(e["date"], e.get("start"), tz),
          "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
          "eventStatus": "https://schema.org/EventScheduled",
          "location": {"@type": "Place", "name": e["venue"], "address": e["address"]},
          "description": re.sub(r"\s*\n\s*", " ", e.get("desc_zh") or ""),
          "image": [image], "url": f"{page}#e-{e['id']}", "isAccessibleForFree": bool(e.get("free")),
          "inLanguage": "zh-CN", "sameAs": e["url"]}
    if e.get("start") and e.get("end"):
        ld["endDate"] = iso(e["date"], e["end"], tz)
    if e.get("free"):
        ld["offers"] = {"@type": "Offer", "price": 0, "priceCurrency": CURRENCY.get(cid, "USD"),
                        "availability": "https://schema.org/InStock", "url": e["url"]}
    return ld

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
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//No Boring Weekends//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
         "X-WR-CALNAME:" + ics_text(f'{SITE["name_zh"]} · {city["zh"]}'), "X-WR-TIMEZONE:" + city["tz"],
         "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    for e in events:
        L += ["BEGIN:VEVENT", f"UID:{e['id']}-{e['date']}@noboringweekends", "DTSTAMP:" + stamp]
        if e.get("start"):
            s = local_dt(e["date"], e["start"], city["tz"])
            en = local_dt(e["date"], e["end"], city["tz"]) if e.get("end") else (s + timedelta(hours=2) if s else None)
            if s:
                f = lambda d: d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                L += ["DTSTART:" + f(s), "DTEND:" + f(en)]
            else:
                L += ["DTSTART;VALUE=DATE:" + e["date"].replace("-", "")]
        else:
            d = datetime.strptime(e["date"], "%Y-%m-%d")
            L += ["DTSTART;VALUE=DATE:" + d.strftime("%Y%m%d"), "DTEND;VALUE=DATE:" + (d + timedelta(days=1)).strftime("%Y%m%d")]
        cost = "免费" if e.get("free") else e.get("cost_zh", "")
        L += ["SUMMARY:" + ics_text(e["title_zh"]), "LOCATION:" + ics_text(e["venue"] + ", " + e["address"]),
              "DESCRIPTION:" + ics_text(f'{e.get("desc_zh","")}\n费用:{cost}\n{e["url"]}'), "URL:" + e["url"], "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in L) + "\r\n"

def replace_block(src, name, new):
    pat = re.compile(r"<!--%s-->.*?<!--/%s-->" % (name, name), re.S)
    if not pat.search(src): sys.exit(f"marker <!--{name}--> missing in index.html")
    return pat.sub(lambda m: new, src, count=1)

def main():
    data = json.load(open(os.path.join(DOCS, "events.json"), encoding="utf-8"))
    cities, wk = data["cities"], data["weekend"]
    rng = f'{md(wk["start"])}–{md(wk["end"])}'
    tpl = open(os.path.join(DOCS, "index.html"), encoding="utf-8").read()
    stamp = data["updated"].replace("-", "") + "T000000Z"  # deterministic, so rebuilds without data changes are no-ops

    # Root page: generic SEO block and crawlable city links.
    root_desc = "北美华人周末活动指南：纽约、湾区、洛杉矶、西雅图、多伦多、温哥华等 %d 个城市的亲子和大人活动，华人与亚裔社区活动优先，每周更新。" % len(cities)
    root = replace_block(tpl, "seo", seo_block("周末不无聊 · 北美华人周末去哪儿", root_desc, URL + "/", URL + "/og/default.png"))
    root = replace_block(root, "citylinks", city_links(cities))
    open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(root)

    os.makedirs(os.path.join(DOCS, "cal"), exist_ok=True)
    urls = [(URL + "/", data["updated"])]
    for cid, c in cities.items():
        evs = sorted(c["events"], key=sort_key)
        page, image = f"{URL}/{cid}/", f"{URL}/og/{cid}.png"
        free = sum(1 for e in evs if e.get("free"))
        title = f'{c["zh"]}周末去哪儿｜{rng} 亲子和大人活动 · {SITE["name_zh"]}'
        picks = "、".join(e["title_zh"] for e in evs[:3])
        desc = (f'{c["zh"]}这个周末（{rng}）{len(evs)} 个活动' + (f'，其中 {free} 个免费' if free else '')
                + (f'：{picks}等' if picks else '') + '。华人与亚裔社区活动优先，每周更新。')
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "WebPage", "@id": page, "url": page, "name": title, "inLanguage": "zh-CN", "description": desc},
            *[event_ld(e, cid, c["tz"], page, image) for e in evs]]}
        extra = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
        out = replace_block(root, "seo", seo_block(title, desc, page, image, extra))
        out = out.replace('<meta charset="utf-8">', '<meta charset="utf-8"><base href="../">', 1)
        out = out.replace('<script src="sky.js"></script>', f'<script>window.PAGE_CITY="{cid}"</script>\n<script src="sky.js"></script>', 1)
        out = out.replace('<h2 id="weekend-title"></h2>', f'<h2 id="weekend-title">{esc(c["zh"])} · {rng} 周末</h2>', 1)
        cards = "".join(card_html(e) for e in evs) or '<p class="empty">这个城市本周的活动还在整理中。</p>'
        out = out.replace('<div class="list" id="list"></div>', f'<div class="list" id="list">{cards}</div>', 1)
        os.makedirs(os.path.join(DOCS, cid), exist_ok=True)
        open(os.path.join(DOCS, cid, "index.html"), "w", encoding="utf-8").write(out)
        open(os.path.join(DOCS, "cal", cid + ".ics"), "w", encoding="utf-8", newline="").write(ics(cid, c, evs, stamp))
        urls.append((page, data["updated"]))

    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{u}</loc><lastmod>{d}</lastmod><changefreq>weekly</changefreq></url>" for u, d in urls]
    sm.append("</urlset>")
    open(os.path.join(DOCS, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm) + "\n")
    open(os.path.join(DOCS, "robots.txt"), "w", encoding="utf-8").write(
        f"User-agent: *\nAllow: /\nDisallow: /xhs.html\n\nSitemap: {URL}/sitemap.xml\n")
    print(f"built {len(cities)} city pages, feeds and sitemap for {URL}")

if __name__ == "__main__":
    main()
