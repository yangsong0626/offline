// Render Xiaohongshu carousels from docs/xhs.html into PNG files plus a caption text file.
// Usage: NODE_PATH=$(npm root -g) node tools/render_xhs.js <out-dir> "city=nyc+nj" "city=nyc+nj&mode=season" ...
// Each query becomes <out-dir>/<city>-<weekend-or-season>/ with 01.png… and caption.txt (title on the first line).
const http = require("http"), fs = require("fs"), path = require("path");
const { chromium } = require("playwright");

const DOCS = path.join(__dirname, "..", "docs");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".png": "image/png", ".svg": "image/svg+xml" };

function serve() {
  const srv = http.createServer((req, res) => {
    const p = path.join(DOCS, decodeURIComponent(req.url.split("?")[0]));
    if (!p.startsWith(DOCS) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(p)] || "application/octet-stream" });
    fs.createReadStream(p).pipe(res);
  });
  return new Promise((ok) => srv.listen(0, "127.0.0.1", () => ok(srv)));
}

(async () => {
  const [out, ...queries] = process.argv.slice(2);
  if (!out || !queries.length) { console.error("usage: render_xhs.js <out-dir> <query> [...]"); process.exit(2); }
  const srv = await serve(), port = srv.address().port, browser = await chromium.launch();
  try {
    for (const q of queries) {
      const page = await browser.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(`http://127.0.0.1:${port}/xhs.html?${q}`, { waitUntil: "networkidle" });
      await page.waitForFunction(() => document.querySelectorAll("#grid img").length > 0 && document.getElementById("title").value, null, { timeout: 30000 });
      const r = await page.evaluate(() => ({
        names: [...document.querySelectorAll("#grid a[download]")].map((a) => a.download),
        urls: [...document.querySelectorAll("#grid img")].map((i) => i.src),
        title: document.getElementById("title").value, body: document.getElementById("body").value,
      }));
      if (errors.length) throw new Error(`${q}: ${errors.join("; ")}`);
      const dir = path.join(out, r.names[0].replace(/-\d+\.png$/, ""));
      fs.mkdirSync(dir, { recursive: true });
      r.urls.forEach((u, i) => fs.writeFileSync(path.join(dir, String(i + 1).padStart(2, "0") + ".png"), Buffer.from(u.split(",")[1], "base64")));
      fs.writeFileSync(path.join(dir, "caption.txt"), r.title + "\n\n" + r.body + "\n");
      console.log(`${dir}: ${r.urls.length} images · ${r.title}`);
      await page.close();
    }
  } finally { await browser.close(); srv.close(); }
})().catch((e) => { console.error(e.message); process.exit(1); });
