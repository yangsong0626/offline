"""Pull public-library events for the libraries in tools/sources.json ("libraries": city -> [...]) from the two
calendar platforms most of them use: BiblioCommons ({name, slug, branches?}, via gateway.bibliocommons.com) and
Communico ({name, platform: "communico", host}, via the host's eeventcaldata JSON). Library programs are free, small and mostly missing from weekend
roundups, so they need their own feed. Writes one JSON object per event to <out>/library_events.jsonl and prints a
per-library count, flagging programs in Chinese (lang) so they can be tiered A.
Usage: python3 tools/fetch_libraries.py <out-dir> [START YYYY-MM-DD] [DAYS] [city ...]   (defaults: today, 21 days)
"""
import html, json, os, re, subprocess, sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://gateway.bibliocommons.com/v2/libraries/{slug}/events?startDate={a}&endDate={b}&limit=100&page={p}"
CHINESE = re.compile(r"chinese|mandarin|cantonese|中文|普通话|國語|粤语|粵語", re.I)

def get_json(url):
    r = subprocess.run(["curl", "-s", "--max-time", "30", "-A", "Mozilla/5.0", url], capture_output=True)
    try: return json.loads(r.stdout)
    except ValueError: return None

def plain(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def pull_communico(lib, a, days):
    req = json.dumps({"private": False, "date": a, "days": days, "locations": [], "ages": [], "types": []})
    r = subprocess.run(["curl", "-s", "-G", "--max-time", "40", f"https://{lib['host']}/eeventcaldata",
                        "--data-urlencode", "event_type=0", "--data-urlencode", f"req={req}"], capture_output=True)
    try: rows = json.loads(r.stdout)
    except ValueError: return [], False
    out = []
    for e in rows if isinstance(rows, list) else []:
        title = (e.get("title") or "").strip()
        if not title or "cancel" in title.lower() or e.get("changed_reason") or e.get("private_event") == "1": continue
        desc = plain(e.get("long_description") or e.get("description"))
        tags = e.get("tagsArray") or []
        out.append({"library": lib["name"], "title": title, "start": (e.get("raw_start_time") or "")[:16].replace(" ", "T"),
                    "end": (e.get("raw_end_time") or "")[:16].replace(" ", "T"), "branch": e.get("location") or "",
                    "room": e.get("venues") or "", "audiences": e.get("agesArray") or [], "types": tags, "languages": [],
                    "chinese": bool(CHINESE.search(" ".join([title, desc] + tags))),
                    "signup": e.get("allow_reg") == "1" or e.get("third_party_reg") == "1",
                    "url": e.get("url") or f"https://{lib['host']}/event/{e.get('id')}", "desc": desc[:400]})
    return out, True

def pull(lib, a, b):
    if lib.get("platform") == "communico":
        return pull_communico(lib, a, (date.fromisoformat(b) - date.fromisoformat(a)).days)
    out, page = [], 1
    while True:
        d = get_json(API.format(slug=lib["slug"], a=a, b=b, p=page))
        if not d or "entities" not in d: return out, d is not None
        ent = d["entities"]
        names = lambda key, ids: [ent.get(key, {}).get(i, {}).get("name", "") for i in ids or []]
        for e in ent.get("events", {}).values():
            df = e.get("definition", {})
            if df.get("isCancelled"): continue
            loc = ent.get("locations", {}).get(df.get("branchLocationId") or "", {})
            if lib.get("branches") and df.get("branchLocationId") not in lib["branches"]: continue
            langs = names("eventLanguages", df.get("languageIds"))
            title, desc = df.get("title", "").strip(), plain(df.get("description"))
            out.append({"library": lib["name"], "title": title, "start": df.get("start"), "end": df.get("end"),
                        "branch": loc.get("name", ""), "room": (df.get("locationDetails") or "").split("\n")[0],
                        "audiences": names("eventAudiences", df.get("audienceIds")), "types": names("eventTypes", df.get("typeIds")),
                        "languages": langs, "chinese": bool(CHINESE.search(" ".join(langs) + " " + title + " " + desc)),
                        "signup": bool((df.get("registrationInfo") or {}).get("enabledMethods")),
                        "url": f"https://{lib['slug']}.bibliocommons.com/events/{e.get('id')}", "desc": desc[:400]})
        pages = (d.get("events", {}).get("pagination") or {}).get("pages") or 1
        if page >= pages: return out, True
        page += 1

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    args = sys.argv[2:]
    start = date.fromisoformat(args.pop(0)) if args and args[0][:2] == "20" else date.today()
    days = int(args.pop(0)) if args and args[0].isdigit() else 21
    only = set(args)
    a, b = start.isoformat(), (start + timedelta(days)).isoformat()
    libs = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8")).get("libraries", {})
    os.makedirs(sys.argv[1], exist_ok=True)
    total = 0
    with open(os.path.join(sys.argv[1], "library_events.jsonl"), "w", encoding="utf-8") as f:
        for city, items in libs.items():
            if only and city not in only: continue
            for lib in items:
                evs, ok = pull(lib, a, b)
                for e in evs: f.write(json.dumps({"city": city, **e}, ensure_ascii=False) + "\n")
                total += len(evs)
                zh = sum(e["chinese"] for e in evs)
                print(f"[{city}] {lib['name']}: {len(evs)} events" + (f", {zh} in/about Chinese" if zh else "") + ("" if ok else " (no response)"))
    print(f"done: {total} events {a}..{b} -> {os.path.join(sys.argv[1], 'library_events.jsonl')}")

if __name__ == "__main__":
    main()
