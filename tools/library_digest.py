"""Turn <dir>/library_events.jsonl (from tools/fetch_libraries.py) into docs/library/<city>.json, the per-city
"图书馆免费活动" box on city pages. Nothing is dropped: every upcoming program is kept and ranked, anything in or about
Chinese first, then weekend, family and special programs, with services (ESL, tech help, legal...) at the bottom;
the same program at several branches on one day is folded into one row.
Usage: python3 tools/library_digest.py <dir>
"""
import json, os, re, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
FAMILY = re.compile(r"kid|child|famil|teen|toddler|baby|preschool|youth|all ages", re.I)
SPECIAL = re.compile(r"festival|celebrat|holiday|perform|concert|music|film|movie|craft|stem|steam|lego|magic|puppet|dance|art|lunar|diwali|thanksgiving|gingerbread|santa", re.I)
# Services rather than outings (often offered in Chinese, so they must outweigh the Chinese bonus).
DULL = re.compile(r"computer|\besl\b|\bell\b|english (conversation|learn|level|class)|basic english|tax|job|resume|career|book club|meeting|tutor|homework|citizenship|tech (help|assist)|assistance|notary|blood|medicare|seminar|housing|legal|renter|tenant|navigator|drop-in hours|immigration|benefits|counsel|settlement|welcoming|resource|services|living skills|device|clinic|troop|girl scout", re.I)

def score(e):
    s = 100 * e["chinese"]
    d = date.fromisoformat(e["start"][:10])
    if d.weekday() >= 5: s += 20
    elif d.weekday() == 4 and e["start"][11:13] >= "17": s += 5
    blob = " ".join([e["title"]] + e["audiences"] + e["types"])
    if FAMILY.search(blob): s += 10
    if SPECIAL.search(blob): s += 10
    if DULL.search(blob): s -= 150
    if re.search(r"story ?time", e["title"], re.I): s -= 5
    return s

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    data = json.load(open(os.path.join(HERE, "..", "docs", "events.json"), encoding="utf-8"))
    win = data.get("week") or data["weekend"]
    today = date.today().isoformat()
    rows = [json.loads(l) for l in open(os.path.join(sys.argv[1], "library_events.jsonl"), encoding="utf-8")]
    groups = {}
    for e in rows:
        if not e.get("start") or e["start"][:10] < today: continue
        key = (e["city"], e["title"].lower().strip(), e["start"][:10])
        g = groups.setdefault(key, {**e, "branches": []})
        if e["branch"] and e["branch"] not in g["branches"]: g["branches"].append(e["branch"])
        if e["start"] < g["start"]: g.update({k: e[k] for k in ("start", "end", "branch", "url")})
    out_dir = os.path.join(HERE, "..", "docs", "library")
    os.makedirs(out_dir, exist_ok=True)
    cities = {}
    for g in groups.values(): cities.setdefault(g["city"], []).append(g)
    for cid in data["cities"]: cities.setdefault(cid, [])  # an empty file for cities without a library feed, so pages don't 404
    for city, gs in sorted(cities.items()):
        # This issue's window first, best first; then everything later, also best first.
        gs.sort(key=lambda g: (g["start"][:10] > win["end"], -score(g), g["start"]))
        events = [{"title": g["title"], "start": g["start"], "end": g.get("end") or "", "lib": g["library"], "branch": g["branch"],
                   "n": len(g["branches"]) or 1, "zh": g["chinese"], "kids": bool(FAMILY.search(" ".join([g["title"]] + g["audiences"]))),
                   "signup": g["signup"], "url": g["url"], "score": score(g)} for g in gs]
        json.dump({"updated": today, "events": events}, open(os.path.join(out_dir, city + ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"{city}: {len(events)} programs ({sum(x['zh'] for x in events)} Chinese)")

if __name__ == "__main__":
    main()
