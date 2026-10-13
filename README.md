# 周末不无聊 No Boring Weekends
Static site: `docs/index.html` + `docs/events.json`. Update `docs/events.json` every Friday.
`editor_notes_zh` / `editor_notes_en` on each city are internal notes for editors and are not shown on the site.
Each event has an `audience` of `family` (亲子), `adult` (大人) or `all` (both). Leave `start` empty when the time is not fixed; the page shows "时间见官网" and calendar exports become all-day events.
Hosting: Cloudflare Pages (build output directory: `docs`, no build command).

## 小红书出图
Open `/xhs.html` on the live site (not linked from the main page). Pick a city to get 3:4 carousel images (1080×1440: cover, event cards, closing page) plus a copy-ready title, caption and hashtags. "保存全部图片" uses the phone share sheet when available, otherwise downloads each PNG.
Landmark silhouettes live in `docs/sky.js` and are shared by both pages.

## App (PWA)
The site installs as an app: `docs/manifest.webmanifest`, icons in `docs/icons/`, and `docs/sw.js` for offline use. Pages and `events.json` load network-first, so weekly updates show up right away; other files are cached. If you change cached files such as `sky.js` or the icons, bump `VERSION` in `sw.js`.
Android/Chrome visitors see an "安装" button; iPhone visitors get "分享 → 添加到主屏幕" instructions. Dismissing the banner hides it for that browser.

## 搜索与 AI 引用（GEO）
主页由 JavaScript 渲染，多数 AI 爬虫不执行 JS，看不到活动内容。`scripts/build_seo.py` 读 `docs/events.json`，生成纯 HTML：
- `docs/zh/<city>/`、`docs/en/<city>/`：每个城市中英文各一个固定网址的「本周末活动」页，每个活动带 schema.org `Event` 结构化数据，互相用 hreflang 关联
- `docs/zh/`、`docs/en/`：城市目录页
- `docs/sitemap.xml`、`docs/robots.txt`（显式放行 AI 搜索爬虫，屏蔽 `xhs.html`）、`docs/llms.txt`
- 主页注入 canonical、hreflang、结构化数据和可抓取的城市链接；主页支持 `?city=nyc&lang=en` 直达

网站地址写在 `site.json`（或环境变量 `SITE_URL`）。推送 `events.json` 后 GitHub Actions 会自动重新生成（`.github/workflows/seo-pages.yml`）；本地手动跑：`python3 scripts/build_seo.py`。
Cloudflare 后台请确认 Security → Bots 里没有开启「Block AI bots」，否则 AI 爬虫会被直接拦截。
