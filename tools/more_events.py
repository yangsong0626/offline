"""Write docs/more.json: every upcoming event found in the source calendars (<dir>/events.jsonl from
tools/fetch_sources.py) that isn't already a full card in docs/events.json, so nothing found is left off the site.
These show in a "🗂️ 更多活动" box on city pages with their original (usually English) titles, sorted by date,
Chinese/Asian community events flagged.
Usage: python3 tools/more_events.py <dir>
"""
import html, json, os, re, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ASIAN = re.compile(r"chinese|china|mandarin|cantonese|taiwan|hong kong|lunar|asian|asia|aapi|japan|korea|filipin|vietnam|"
                   r"chinatown|moca|lantern|dim sum|[一-鿿]", re.I)

def norm(s): return re.sub(r"[^a-z0-9一-鿿]+", "", (s or "").lower())

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ev = json.load(open(os.path.join(HERE, "..", "docs", "events.json"), encoding="utf-8"))
    today = date.today().isoformat()
    have = {cid: ({e["url"] for e in c["events"]}, [norm(e["title_en"]) for e in c["events"]]) for cid, c in ev["cities"].items()}
    out, seen = {}, set()
    for line in open(os.path.join(sys.argv[1], "events.jsonl"), encoding="utf-8"):
        x = json.loads(line)
        cid, name, start = x["city"], html.unescape(x.get("name") or "").strip(), x.get("start") or ""
        if cid not in have or not name or start[:10] < today: continue
        urls, titles = have[cid]
        n = norm(name)
        if x.get("url") in urls or any(n and (n in t or t in n) for t in titles if len(t) > 8): continue
        if (cid, n, start[:10]) in seen: continue
        seen.add((cid, n, start[:10]))
        out.setdefault(cid, []).append({"title": name, "start": start[:16], "end": (x.get("end") or "")[:16], "place": html.unescape(x.get("place") or ""),
                                        "address": x.get("address") or "", "free": x.get("free"), "url": x.get("url") or x.get("source"),
                                        "asian": bool(ASIAN.search(name + " " + (x.get("place") or "")))})
    for xs in out.values(): xs.sort(key=lambda e: e["start"])
    path = os.path.join(HERE, "..", "docs", "more.json")
    json.dump({"updated": today, "cities": out}, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for cid, xs in sorted(out.items()): print(f"{cid}: {len(xs)} more ({sum(e['asian'] for e in xs)} Chinese/Asian)")

if __name__ == "__main__":
    main()
