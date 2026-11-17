"""Fetch the calendar pages listed in tools/sources.json ("urls" on a source) and save, per page:
  <out>/<host>.txt         readable text (scripts, styles and tags stripped)
  <out>/events.jsonl       schema.org Event entries found in the pages' JSON-LD (name, dates, place, url)
Usage: python3 tools/fetch_sources.py <out-dir> [YYYY-MM-DD] [city ...]   (no city = all; "national" is a valid name)
URLs may contain {mon} {fri} {sun} {sunmon} {year}, filled from the Friday on or after the date (default today).
Hosts must be on the environment's network allowlist; blocked or failing pages are reported and skipped.
"""
import html, json, os, re, subprocess, sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

def get(url):
    # curl rather than urllib: it is already set up for the environment's proxy and CA bundle.
    r = subprocess.run(["curl", "-s", "-L", "--max-time", "25", "-A", UA, "-w", "\n%{http_code}", url], capture_output=True)
    body, _, code = r.stdout.decode("utf-8", "replace").rpartition("\n")
    return (body if code == "200" else None), code

def text_of(page):
    page = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|article|section)>", "\n", page)
    page = html.unescape(re.sub(r"<[^>]+>", " ", page))
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in page.split("\n")]
    return "\n".join(l for l in lines if l)

def ld_events(page, url):
    out = []
    for blob in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page):
        try: data = json.loads(blob.strip())
        except ValueError: continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            x = stack.pop()
            if isinstance(x, list): stack.extend(x); continue
            if not isinstance(x, dict): continue
            stack.extend(v for k, v in x.items() if k in ("@graph", "itemListElement", "item", "subEvent"))
            t = x.get("@type")
            if t == "Event" or (isinstance(t, list) and "Event" in t) or (isinstance(t, str) and t.endswith("Event")):
                loc = x.get("location") or {}
                if isinstance(loc, list): loc = loc[0] if loc else {}
                addr = loc.get("address") if isinstance(loc, dict) else ""
                if isinstance(addr, dict): addr = ", ".join(str(addr.get(k, "")) for k in ("streetAddress", "addressLocality", "addressRegion") if addr.get(k))
                out.append({"name": x.get("name"), "start": x.get("startDate"), "end": x.get("endDate"),
                            "place": loc.get("name") if isinstance(loc, dict) else str(loc), "address": addr,
                            "url": x.get("url") or url, "free": x.get("isAccessibleForFree"), "source": url})
    return out

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    args = sys.argv[2:]
    day = date.fromisoformat(args.pop(0)) if args and args[0][:2] == "20" else date.today()
    fri = day + timedelta((4 - day.weekday()) % 7); sun = fri + timedelta(2)
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    fill = dict(mon=months[fri.month - 1], fri=fri.day, sun=sun.day, sunmon=months[sun.month - 1], year=sun.year)
    out, only = sys.argv[1], set(args)
    src = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8"))
    groups = {"national": src["national"], **src["cities"]}
    os.makedirs(out, exist_ok=True)
    found = 0
    with open(os.path.join(out, "events.jsonl"), "w", encoding="utf-8") as ev:
        for city, items in groups.items():
            if only and city not in only: continue
            for s in items:
                for url in (u.format(**fill) for u in s.get("urls", [])):
                    page, code = get(url)
                    if page is None:
                        print(f"[{city}] {s['name']}: HTTP {code}, skipped"); continue
                    name = re.sub(r"[^\w.-]+", "_", url.split("//", 1)[1])[:80]
                    open(os.path.join(out, f"{city}--{name}.txt"), "w", encoding="utf-8").write(f"{url}\n\n{text_of(page)}")
                    evs = ld_events(page, url)
                    for e in evs: ev.write(json.dumps({"city": city, **e}, ensure_ascii=False) + "\n")
                    found += len(evs)
                    print(f"[{city}] {s['name']}: ok, {len(evs)} structured events")
    print(f"done: {found} structured events -> {os.path.join(out, 'events.jsonl')}")

if __name__ == "__main__":
    main()
