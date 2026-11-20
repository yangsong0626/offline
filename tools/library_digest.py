"""Turn <dir>/library_events.jsonl (from tools/fetch_libraries.py) into docs/library.json, the per-city
"图书馆免费活动" list on city pages. Libraries post hundreds of programs a week, so this keeps the ones worth
showing: anything in or about Chinese first, then weekend and family programs, with the same program at several
branches on one day folded into one row. Programs in Chinese further out (up to the fetch horizon) are kept too.
Usage: python3 tools/library_digest.py <dir> [PER_CITY=25]
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
    per = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    data = json.load(open(os.path.join(HERE, "..", "docs", "events.json"), encoding="utf-8"))
    win = data.get("week") or data["weekend"]
    today = date.today().isoformat()
    rows = [json.loads(l) for l in open(os.path.join(sys.argv[1], "library_events.jsonl"), encoding="utf-8")]
    groups = {}
    for e in rows:
        if not e.get("start") or e["start"][:10] < today: continue
        key = (e["city"], e["title"].lower().strip(), e["start"][:10])
        g = groups.setdefault(key, {**e, "n": 0, "branches": []})
        g["n"] += 1
        if e["branch"] and e["branch"] not in g["branches"]: g["branches"].append(e["branch"])
        if e["start"] < g["start"]: g.update({k: e[k] for k in ("start", "end", "branch", "url")})
    out = {}
    for (city, _, _), g in groups.items():
        out.setdefault(city, []).append(g)
    cities = {}
    for city, gs in out.items():
        now = [g for g in gs if g["start"][:10] <= win["end"]]
        later = [g for g in gs if g["start"][:10] > win["end"] and g["chinese"] and score(g) > 0]
        now.sort(key=lambda g: (-score(g), g["start"]))
        later.sort(key=lambda g: g["start"])
        pick = [g for g in now if score(g) > 0][:per] + later[:10]
        pick.sort(key=lambda g: g["start"])
        cities[city] = [{"title": g["title"], "start": g["start"], "end": g.get("end") or "", "lib": g["library"],
                         "branch": g["branch"], "n": len(g["branches"]) or 1, "zh": g["chinese"],
                         "kids": bool(FAMILY.search(" ".join([g["title"]] + g["audiences"]))), "signup": g["signup"],
                         "url": g["url"]} for g in pick]
    path = os.path.join(HERE, "..", "docs", "library.json")
    json.dump({"updated": today, "cities": cities}, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for c, xs in cities.items():
        print(f"{c}: {len(xs)} shown ({sum(x['zh'] for x in xs)} Chinese)")

if __name__ == "__main__":
    main()
