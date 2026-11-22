# 周末不无聊 No Boring Weekends
Static site: `docs/index.html` + `docs/events.json`. Update `docs/events.json` every Friday with that weekend plus the following Mon–Thu: `weekend` is Fri–Sun, the optional `week` range (Fri–Thu) covers the weekday events. Events whose date has passed are hidden on the page. Events dated after `week.end` can stay in the file: they show under the 「之后 / Later」 chip, so keep anything good found for later dates instead of dropping it, and carry still-upcoming ones forward each week.
`editor_notes_zh` / `editor_notes_en` on each city are internal notes for editors and are not shown on the site.
Each event has an `audience` of `family` (亲子), `adult` (大人) or `all` (both). Top picks can carry `why_zh`/`why_en` (值得期待的瞬间: describe the moment people will remember, e.g. the lights switching on, not just "has light displays") and `tips_zh`/`tips_en` (age fit, parking or transit, rain plan, crowds), shown in a highlighted box on the card and on Xiaohongshu cards. Leave `start` empty when the time is not fixed; the page shows "时间见官网" and calendar exports become all-day events.
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
The "内容" menu switches between this weekend's events, the seasonal guide (`seasonal.json`, exhibitions left out) and 提前订票 (seasonal items and this week's events that need tickets and have `tips_zh`); `nyc+nj` and `la+oc` combine two cities into one carousel. To render without a browser: `NODE_PATH=$(npm root -g) node tools/render_xhs.js <out-dir> "city=nyc+nj" "city=nyc+nj&mode=season"` writes the PNGs and a `caption.txt` (title on the first line) per carousel. For a single long-form post (长文) instead of a carousel, so nothing depends on image order: `python3 tools/xhs_article.py <out-file> nyc+nj` writes the title and a day-by-day article (time, cost, place, ✨ moment, 📝 tips) to paste into the 长文 editor.
Landmark silhouettes live in `docs/sky.js` and are shared by both pages.

## Distance from you

Events and seasonal items carry `"geo": [lat, lng]`, added by `python3 tools/geocode.py` after each data update (US addresses via the Census geocoder, Canada and US misses via OpenStreetMap Nominatim; cached in `tools/geocache.json`; vague addresses like "Vancouver area" are skipped). On a city page the 📍 离我最近 / Nearest chip asks for the browser's location, shows straight-line distance on each card (miles in the US, km in Canada) and sorts by it. The location is rounded to ~100 m and kept only in the visitor's localStorage; nothing is sent anywhere. Visitors who would rather not share location can type a US ZIP or Canadian postal code in the city box: it is looked up in `docs/zips.json` (built once by `python3 tools/zips.py <download-dir>` from the GeoNames postal code dumps, CC BY 4.0, ~11k codes near the covered cities, loaded only when a code is entered), switches city and sorts by distance from that code, again entirely in the browser.

## App (PWA)
The site installs as an app: `docs/manifest.webmanifest`, icons in `docs/icons/`, and `docs/sw.js` for offline use. Pages and `events.json` load network-first, so weekly updates show up right away; other files are cached. If you change cached files such as `sky.js` or the icons, bump `VERSION` in `sw.js`.
Android/Chrome visitors see an "安装" button; iPhone visitors get "分享 → 添加到主屏幕" instructions. Dismissing the banner hides it for that browser.

## Free days & discounts (`docs/deals.json`)
Recurring rules instead of dated events, so one entry keeps working every week. Each deal has `cities`, bilingual title / eligibility (`who_*`) / description, `url`, `verified` (last checked) and a `rule`:
- `{"type":"weekly","days":[5]}` — every Friday (0 = Sunday … 6 = Saturday)
- `{"type":"monthly","nth":2,"day":0}` — second Sunday of each month
- `{"type":"first_full_weekend"}` — first Saturday of the month and the Sunday after (Bank of America Museums on Us)
- `{"type":"always"}` — any day the eligibility applies (residents, students, library cards)

Optional fields: `"months":[11,12,1]` limits a rule to a season, `"skip":["YYYY-MM-DD"]` drops a date the venue cancelled or moved, `"extra":["YYYY-MM-DD"]` adds a one-off date, and `nth` can be a list (`[1,2]` = first and second Sunday).

City pages show a collapsed "💸 本周能用的免费 / 优惠" box computed from these rules, and the build writes a guide per city at `/<city>/guides/free/` and `/en/<city>/guides/free/` with a 5-week free-day calendar. Re-check rules every few months and update `verified`. The rule logic is in `tools/deals.py` and mirrored in `docs/index.html` (`dealOn`); keep them in sync.

## Seasonal attractions (`docs/seasonal.json`)
Long-running things (holiday lights, markets, rinks, holiday shows, exhibitions) live here instead of in `events.json`, so they are entered once per season. `season` names the current season (`slug` becomes the guide path, e.g. `winter`). Each item has `city`, `tier`, `cat` (`lights`, `market`, `rink`, `train`, `show`, `parade`, `exhibit`), `audience`, `start` (null = already open), `end`, optional `days` (open weekdays, 0 = Sunday; null = every day) and `closed` dates, bilingual title / hours / cost / description, `venue`, `address`, `url`.

City pages show a collapsed "🎄 季节限定 · 本周开放" box: items open on a remaining day of this week, plus ones opening in the next three weeks, tagged 本周新开 / X 开幕 / X 结束. The build writes a season guide per city at `/<city>/guides/<slug>/` (and `/en/...`). Fill it at the start of each season, check for closures or date changes in the Friday update, and only list a seasonal item's opening night or special nights in `events.json`.

## Weekly sources (`tools/sources.json`)
Where to look each week, per city: weekend roundups, family sites, parks, and Chinese / Asian community calendars (museums, Chinatown associations, Chinese-language forums), plus national sources. `python3 tools/sources.py [YYYY-MM-DD] [city ...]` prints that week's plan: three searches per city (weekend, Chinese/Asian community, Mon–Thu), each with the `allowed_domains` to restrict a WebSearch to. Add a domain whenever a good source turns up in a weekly search; drop ones that stop publishing.
Sources with `urls` are fetched directly (their hosts are on the environment's network allowlist): `python3 tools/fetch_sources.py <out-dir> [YYYY-MM-DD] [city ...]` saves each page as readable text and collects any schema.org `Event` JSON-LD into `events.jsonl` (name, dates, place, url), which is the most reliable starting point. URLs can use `{mon} {fri} {sun} {sunmon} {year}` for weekly articles. Pages that answer 403/429 or redirect to a host that isn't allowed are skipped; search those with `allowed_domains` instead.

## Library programs (`docs/library/<city>.json`)
Public libraries post hundreds of free programs a week that weekend roundups skip, so they come from the libraries' own feeds instead of the weekly hand-picked list. `tools/sources.json` → `libraries` lists BiblioCommons systems (Toronto, Markham, Vancouver, Richmond BC, Santa Clara County / San José / Alameda / San Mateo / Contra Costa, King County, Boston, Chicago, Harris County, Fulton County) and Communico ones (`platform: "communico"`, `host`: Edison, Princeton, Somerset County, Franklin Township in NJ; Queens Public Library, whose calendar is empty while it recovers from a ransomware attack). Each week:
`python3 tools/fetch_libraries.py <dir> [YYYY-MM-DD] [days]` pulls their events through gateway.bibliocommons.com (programs in or about Chinese are flagged), then `python3 tools/library_digest.py <dir>` writes `docs/library/<city>.json` with every upcoming program, nothing dropped: ranked with this week first, then programs in or about Chinese, weekend, family and special programs, services (ESL, tech help, legal, housing…) last; the same program at several branches on one day is folded into one row. City pages show a collapsed "📚 图书馆免费活动" box with filters (本周 / 周末 / 中文 / 亲子), 30 rows at a time.

## More events (`docs/more.json`)

Events found in the source calendars (`tools/fetch_sources.py` → `events.jsonl`) that are not yet full cards in `events.json` are not discarded: `python3 tools/more_events.py <dir>` writes them to `docs/more.json` and city pages list them in a "🗂️ 更多活动" box with their original titles, by date (Chinese/Asian first on zh pages). Libraries that block automated access (NYPL, Brooklyn) or use other platforms (LAPL, SFPL, Seattle, DC, OC, San Diego, Houston, Dallas) are covered by the weekly free-events search for now.
