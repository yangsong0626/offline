# 周末不无聊 No Boring Weekends
Static site: `docs/index.html` + `docs/events.json`. Update `docs/events.json` every Friday.
`editor_notes_zh` / `editor_notes_en` on each city are internal notes for editors and are not shown on the site.
Each event has an `audience` of `family` (亲子), `adult` (大人) or `all` (both). Leave `start` empty when the time is not fixed; the page shows "时间见官网" and calendar exports become all-day events.
Hosting: Cloudflare Pages (build output directory: `docs`, no build command).
