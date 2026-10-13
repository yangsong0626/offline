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
