# 周末不无聊 No Boring Weekends
Static site: `docs/index.html` + `docs/events.json`. Update `docs/events.json` every Friday.
`editor_notes_zh` / `editor_notes_en` on each city are internal notes for editors and are not shown on the site.
Each event has an `audience` of `family` (亲子), `adult` (大人) or `all` (both). Leave `start` empty when the time is not fixed; the page shows "时间见官网" and calendar exports become all-day events.
Hosting: Cloudflare Pages — **build command `python3 tools/build.py`**, build output directory `docs`.

## Build (SEO, share cards, calendar feeds)
`tools/build.py` (Python stdlib only) reads `docs/events.json` and writes:
- `docs/<city>/index.html` (Chinese) and `docs/en/<city>/index.html` (English) — full site pages with their own title, description, canonical URL, hreflang, Open Graph tags, prerendered event cards and schema.org `Event` JSON-LD; plus `docs/en/index.html`
- `docs/cal/<city>.ics` — subscribable calendar feed per city (the page's "📅 订阅" menu)
- `docs/sitemap.xml` (with hreflang alternates), `docs/robots.txt` (search engines and AI crawlers allowed, `/xhs.html` excluded), `docs/llms.txt` (site summary for AI search)
- the SEO block / city links inside `docs/index.html` (between `<!--seo-->` and `<!--citylinks-->` markers)

Cloudflare runs it on every deploy, so editing `events.json` is still the only weekly step. The generated files are also committed so the site works if the build step is skipped; run `python3 tools/build.py` locally to refresh them.
Set the public site URL in `tools/site.json` (or the `SITE_URL` environment variable). Share images live in `docs/og/` (1200×630, one per city plus `default.png`).

## 小红书出图
Open `/xhs.html` on the live site (not linked from the main page). Pick a city to get 3:4 carousel images (1080×1440: cover, event cards, closing page) plus a copy-ready title, caption and hashtags. "保存全部图片" uses the phone share sheet when available, otherwise downloads each PNG.
Landmark silhouettes live in `docs/sky.js` and are shared by both pages.

## App (PWA)
The site installs as an app: `docs/manifest.webmanifest`, icons in `docs/icons/`, and `docs/sw.js` for offline use. Pages and `events.json` load network-first, so weekly updates show up right away; other files are cached. If you change cached files such as `sky.js` or the icons, bump `VERSION` in `sw.js`.
Android/Chrome visitors see an "安装" button; iPhone visitors get "分享 → 添加到主屏幕" instructions. Dismissing the banner hides it for that browser.

## Free days & discounts (`docs/deals.json`)
Recurring rules instead of dated events, so one entry keeps working every week. Each deal has `cities`, bilingual title / eligibility (`who_*`) / description, `url`, `verified` (last checked) and a `rule`:
- `{"type":"weekly","days":[5]}` — every Friday (0 = Sunday … 6 = Saturday)
- `{"type":"monthly","nth":2,"day":0}` — second Sunday of each month
- `{"type":"first_full_weekend"}` — first Saturday of the month and the Sunday after (Bank of America Museums on Us)
- `{"type":"always"}` — any day the eligibility applies (residents, students, library cards)

City pages show a "💸 本周末能用的免费 / 优惠" box computed from these rules, and the build writes a guide per city at `/<city>/guides/free/` and `/en/<city>/guides/free/` with a 5-week free-day calendar. Re-check rules every few months and update `verified`. The rule logic is in `tools/deals.py` and mirrored in `docs/index.html` (`dealOn`); keep them in sync.
