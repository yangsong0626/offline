"""Add coordinates ("geo": [lat, lng]) to every event in docs/events.json and seasonal item in docs/seasonal.json,
so city pages can show how far each one is from the visitor. US addresses go to the Census geocoder, everything
else (and US misses, e.g. intersections) to OpenStreetMap Nominatim at its 1-request-per-second limit. Results are
cached in tools/geocache.json, so a weekly run only looks up new addresses. A hit far from the rest of its city
(>250 km from the median; NJ spans Cape May to the Hudson) is treated as a wrong match and dropped.
Usage: python3 tools/geocode.py
"""
import json, math, os, re, statistics, subprocess, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "..", "docs")
CACHE = os.path.join(HERE, "geocache.json")
CANADA = {"tor", "van"}
UA = "noboringweekends-geocoder/1.0"
_last = [0.0]

def get(url):
    r = subprocess.run(["curl", "-s", "--max-time", "30", "-A", UA, url], capture_output=True)
    try: return json.loads(r.stdout)
    except ValueError: return None

def census(addr):
    d = get("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?benchmark=Public_AR_Current&format=json&address="
            + urllib.parse.quote(addr))
    m = ((d or {}).get("result") or {}).get("addressMatches") or []
    return [m[0]["coordinates"]["y"], m[0]["coordinates"]["x"]] if m else None

def nominatim(q, cc):
    wait = 1.1 - (time.time() - _last[0])
    if wait > 0: time.sleep(wait)
    _last[0] = time.time()
    d = get(f"https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes={cc}&q=" + urllib.parse.quote(q))
    return [float(d[0]["lat"]), float(d[0]["lon"])] if d else None

VAGUE = re.compile(r"\barea\b|see website|tbd|various", re.I)  # "Vancouver area, BC": a distance would mislead

def lookup(venue, addr, canada):
    if VAGUE.search(addr): return None
    cc = "ca" if canada else "us"
    hit = None if canada or not re.search(r"\d", addr.split(",")[0]) else census(addr)
    hit = hit or nominatim(addr, cc) or nominatim(f"{venue}, {addr}", cc)
    if not hit and "," in addr:  # drop the street part: "Pier 17, 89 South St, New York" -> "89 South St, New York"
        hit = nominatim(addr.split(",", 1)[1].strip(), cc)
    return [round(hit[0], 5), round(hit[1], 5)] if hit else None

def km(a, b):
    p1, p2, dl = math.radians(a[0]), math.radians(b[0]), math.radians(b[1] - a[1])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))

def main():
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    ev_path, sz_path = os.path.join(DOCS, "events.json"), os.path.join(DOCS, "seasonal.json")
    ev = json.load(open(ev_path, encoding="utf-8"))
    sz = json.load(open(sz_path, encoding="utf-8")) if os.path.exists(sz_path) else {"items": []}
    rows = [(cid, e) for cid, c in ev["cities"].items() for e in c["events"]] + [(x["city"], x) for x in sz["items"]]
    new = 0
    for cid, x in rows:
        addr = (x.get("address") or "").strip()
        if not addr: continue
        key = f"{cid}|{addr}"
        if key not in cache:
            cache[key] = lookup(x.get("venue") or "", addr, cid in CANADA)
            new += 1
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    # A city's events sit within a metro area; anything far from the median is a wrong match.
    by_city = {}
    for cid, x in rows:
        g = cache.get(f"{cid}|{(x.get('address') or '').strip()}")
        if g: by_city.setdefault(cid, []).append(g)
    mid = {c: [statistics.median(p[0] for p in ps), statistics.median(p[1] for p in ps)] for c, ps in by_city.items()}
    missing, far = [], []
    for cid, x in rows:
        addr = (x.get("address") or "").strip()
        g = cache.get(f"{cid}|{addr}")
        if g and km(g, mid[cid]) > 250: far.append(f"{cid}: {addr}"); g = None
        if g: x["geo"] = g
        else:
            x.pop("geo", None)
            if addr: missing.append(f"{cid}: {addr}")
    json.dump(ev, open(ev_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    if sz["items"]: json.dump(sz, open(sz_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(rows)} items, {new} new lookups, {len(rows) - len(missing) - len(far)} with coordinates")
    for m in sorted(set(missing)): print("  no match:", m)
    for m in sorted(set(far)): print("  too far from city, dropped:", m)

if __name__ == "__main__":
    main()
