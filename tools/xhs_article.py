"""Write this weekend's picks as one Xiaohongshu long-form post (长文), so a post doesn't depend on a dozen images
staying in order. Output is plain text with "## " day headings, which the 长文 editor keeps as headings.
Usage: python3 tools/xhs_article.py <out-file> [city[+city...]=nyc+nj]
"""
import json, os, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
WD = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
AUD = {"family": "亲子", "adult": "大人", "all": "大人小孩都合适"}

def md(d): return f"{int(d[5:7])}/{int(d[8:10])}"

def article(data, ids):
    wk = data["weekend"]
    cities = [data["cities"][k] for k in ids]
    name = "·".join(c["zh"] for c in cities)
    evs = [e for c in cities for e in c["events"] if wk["start"] <= e["date"] <= wk["end"]]
    evs.sort(key=lambda e: (e["date"], e["tier"] != "A", e.get("start") or "99"))
    free = sum(e["free"] for e in evs)
    zh = sum(e["tier"] == "A" for e in evs)
    title = f"{name}周末去哪儿｜{md(wk['start'])}-{md(wk['end'])}"
    if len(title) > 20: title = f"{name}周末去哪儿｜{len(evs)}个活动"  # XHS title limit
    if len(title) > 20: title = f"{name.replace('·', '')}周末去哪｜{len(evs)}个"
    out = [f"这个周末（{md(wk['start'])}–{md(wk['end'])}）{name}有什么好玩的？一共 {len(evs)} 个活动，"
           f"{free} 个免费，{zh} 个华人活动 🇨🇳，按日期排好了，收藏慢慢看👇", ""]
    day = None
    for e in evs:
        if e["date"] != day:
            day = e["date"]
            out += [f"## {WD[date.fromisoformat(day).weekday()]} {md(day)}", ""]
        mark = "🇨🇳 " if e["tier"] == "A" else ""
        out.append(f"▪️ {mark}{e['title_zh']}")
        when = (e["start"] + ("–" + e["end"] if e.get("end") else "")) if e.get("start") else "时间见官网"
        out.append(f"🕐 {when}｜💰 {'免费' if e['free'] else e['cost_zh']}｜{AUD.get(e.get('audience') or 'family')}")
        out.append(f"📍 {e['venue']} · {e['area']}")
        if e.get("why_zh"): out.append(f"✨ {e['why_zh']}")
        if e.get("tips_zh"): out.append(f"📝 {e['tips_zh']}")
        elif e.get("desc_zh"): out.append(e["desc_zh"])
        out.append("")
    out += ["⚠️ 时间、价格可能变动，出发前请看活动官网", "📌 完整清单、地址和一键加日历在主页简介",
            "⏰ 每周五更新，收藏关注不迷路～"]
    return title, "\n".join(out)

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ids = (sys.argv[2] if len(sys.argv) > 2 else "nyc+nj").split("+")
    data = json.load(open(os.path.join(HERE, "..", "docs", "events.json"), encoding="utf-8"))
    title, body = article(data, ids)
    open(sys.argv[1], "w", encoding="utf-8").write(title + "\n\n" + body + "\n")
    print(f"{sys.argv[1]}: title {len(title)} chars, body {len(body)} chars")

if __name__ == "__main__":
    main()
