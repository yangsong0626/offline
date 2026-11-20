"""Print this week's search plan from tools/sources.json: per city, the WebSearch queries to run and the
allowed_domains to restrict each one to. Usage: python3 tools/sources.py [FRIDAY as YYYY-MM-DD] [city ...]

Each city gets four searches: weekend roundups + family sites, Chinese/Asian community sites, free events
(free-event sites, parks, libraries without a feed), and the following Mon-Thu. Searches restricted to a source list are far less noisy than open web searches.
"""
import json, os, sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def span(a, b):
    return f"{MON[a.month-1]} {a.day}-{b.day} {a.year}" if a.month == b.month else f"{MON[a.month-1]} {a.day} - {MON[b.month-1]} {b.day} {b.year}"

def plan(friday, only=()):
    src = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8"))
    names = {k: c["en"] for k, c in json.load(open(os.path.join(HERE, "..", "docs", "events.json"), encoding="utf-8"))["cities"].items()}
    sun, mon, thu = friday + timedelta(2), friday + timedelta(3), friday + timedelta(6)
    national = {t: [s["domain"] for s in src["national"] if s["type"] == t] for t in ("family", "roundup", "music", "asian")}
    out = []
    for cid, items in src["cities"].items():
        if only and cid not in only: continue
        by = lambda *types: [s["domain"] for s in items if s["type"] in types]
        uniq = lambda xs: list(dict.fromkeys(xs))
        city = names.get(cid, cid)
        out.append({"city": cid, "searches": [
            {"query": f"{city} things to do this weekend {span(friday, sun)} family kids events",
             "allowed_domains": uniq(by("roundup", "family", "parks", "news") + national["family"] + national["roundup"])},
            {"query": f"{city} Chinese Asian community event {span(friday, thu)}",
             "allowed_domains": uniq(by("chinese", "asian") + national["asian"])},
            {"query": f"{city} free events this weekend {span(friday, sun)} free family library park",
             "allowed_domains": uniq(by("free", "library", "parks", "family"))},
            {"query": f"{city} events {span(mon, thu)} weeknight",
             "allowed_domains": uniq(by("roundup", "music", "parks") + national["music"])},
        ]})
    return out

if __name__ == "__main__":
    args = sys.argv[1:]
    day = date.fromisoformat(args.pop(0)) if args and args[0][:2] == "20" else date.today()
    friday = day + timedelta((4 - day.weekday()) % 7)
    for c in plan(friday, set(args)):
        print(f"## {c['city']}")
        for s in c["searches"]:
            print(f"- {s['query']}\n  allowed_domains: {', '.join(s['allowed_domains'])}")
