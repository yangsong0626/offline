"""Build docs/zips.json: postal code -> [lat, lng] for the areas the site covers, so a visitor can type a ZIP
(or a Canadian postal code) and see distances without their location leaving the browser. US: every ZIP within
160 km of one of the site's cities; Canada: forward sortation areas (first 3 characters) starting M, L or V.
Data: GeoNames postal code dumps (CC BY 4.0, https://download.geonames.org/export/zip/), downloaded with curl.
Rerun only when cities change. Usage: python3 tools/zips.py <download-dir>
"""
import io, json, os, statistics, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from geocode import km  # noqa: E402

def rows(d, cc):
    path = os.path.join(d, cc + ".zip")
    if not os.path.exists(path):
        subprocess.run(["curl", "-s", "--max-time", "120", "-o", path, f"https://download.geonames.org/export/zip/{cc}.zip"], check=True)
    for line in zipfile.ZipFile(path).read(cc + ".txt").decode("utf-8").splitlines():
        f = line.split("\t")
        if len(f) > 10 and f[9] and f[10]: yield f[1], [round(float(f[9]), 3), round(float(f[10]), 3)]

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    d = sys.argv[1]; os.makedirs(d, exist_ok=True)
    ev = json.load(open(os.path.join(HERE, "..", "docs", "events.json"), encoding="utf-8"))
    centers = []
    for cid, c in ev["cities"].items():
        ps = [e["geo"] for e in c["events"] if e.get("geo")]
        if ps: centers.append([statistics.median(p[0] for p in ps), statistics.median(p[1] for p in ps)])
    out = {}
    for code, g in rows(d, "US"):
        if any(km(g, c) <= 160 for c in centers): out[code] = g
    for code, g in rows(d, "CA"):
        if code[:1] in "MLV": out[code] = g
    path = os.path.join(HERE, "..", "docs", "zips.json")
    json.dump(out, open(path, "w", encoding="utf-8"), separators=(",", ":"), sort_keys=True)
    print(f"{len(out)} postal codes -> {path} ({os.path.getsize(path) // 1024} KB)")

if __name__ == "__main__":
    main()
