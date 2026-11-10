// Frame-time benchmark for the "next" UI: production bundle + synthetic mock API.
//
//   npm run build && npm run preview:mock          (in one terminal)
//   npm i --no-save puppeteer-core && node bench/frames.mjs
//
// Env: URL (default http://localhost:4173), CHROME (path to Chrome), THROTTLE=4 for a
// slow-CPU pass, MOBILE=1 for 375x812. A frame counts as dropped for each 16.7ms budget
// it overruns, so "smooth" is the share of 60fps frames delivered on time.
// Each scenario records every requestAnimationFrame delta and every long task (>50ms).
import puppeteer from "puppeteer-core";

const URL = process.env.URL ?? "http://localhost:4173";
const THROTTLE = Number(process.env.THROTTLE ?? 1);
const MOBILE = process.env.MOBILE === "1";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME ?? "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: "new",
  args: ["--enable-gpu-rasterization", "--ignore-gpu-blocklist", "--disable-background-timer-throttling", "--disable-renderer-backgrounding"],
});
const page = await browser.newPage();
await page.setViewport(MOBILE ? { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true, hasTouch: true } : { width: 1440, height: 900, deviceScaleFactor: 1 });
// Turkish pins the label selectors below; 4821 is the mock API's synthetic Portfolio Code.
await page.evaluateOnNewDocument(() => { localStorage.setItem("fadir.ui", "next"); localStorage.setItem("fadir.lang", "tr"); });
const cdp = await page.createCDPSession();
if (THROTTLE > 1) await cdp.send("Emulation.setCPUThrottlingRate", { rate: THROTTLE });

await page.goto(`${URL}/#/genel`, { waitUntil: "networkidle0" });
await page.evaluate(() => fetch("/api/access/code", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: "4821" }) }));
await page.reload({ waitUntil: "networkidle0" });
await sleep(2500);

await page.evaluate(() => {
  window.__frames = [];
  window.__long = [];
  window.__rec = false;
  let last = performance.now();
  const loop = (t) => { if (window.__rec) window.__frames.push(t - last); last = t; requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
  new PerformanceObserver((list) => { if (window.__rec) for (const e of list.getEntries()) window.__long.push(e.duration); }).observe({ type: "longtask", buffered: false });
});

async function measure(name, fn) {
  await page.evaluate(() => { window.__frames = []; window.__long = []; window.__rec = true; });
  await fn();
  const r = await page.evaluate(() => { window.__rec = false; return { f: window.__frames, l: window.__long }; });
  const f = r.f.slice(1);
  const s = [...f].sort((a, b) => a - b);
  const dropped = f.reduce((n, d) => n + Math.max(0, Math.round(d / 16.67) - 1), 0);
  const expected = f.reduce((a, b) => a + b, 0) / 16.67;
  const row = {
    scenario: name, frames: f.length,
    fps: (1000 / (f.reduce((a, b) => a + b, 0) / f.length)).toFixed(1),
    p95ms: s[Math.floor(s.length * 0.95)]?.toFixed(1), p99ms: s[Math.floor(s.length * 0.99)]?.toFixed(1), maxms: s.at(-1)?.toFixed(1),
    dropped, smooth: `${(100 * (1 - dropped / Math.max(1, expected))).toFixed(1)}%`,
    longTasks: r.l.length, worstTask: r.l.length ? Math.max(...r.l).toFixed(0) : "0",
  };
  results.push(row);
}

const results = [];
const click = (sel) => page.evaluate((s) => document.querySelector(s)?.click(), sel);
const clickText = (sel, text) => page.evaluate((s, t) => [...document.querySelectorAll(s)].find((e) => e.textContent.trim() === t)?.click(), sel, text);

await measure("idle (ambient bg, live pulse)", () => sleep(3000));

await measure("scroll overview top→bottom→top", async () => {
  for (const dir of [1, -1]) for (let i = 0; i < 30; i++) { await page.mouse.wheel({ deltaY: 90 * dir }); await sleep(40); }
  await sleep(300);
});

await page.evaluate(() => document.getElementById("grafik").scrollIntoView({ block: "center" }));
await sleep(500);
const box = await page.evaluate(() => { const b = document.querySelector(".vchart canvas").getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height }; });

await measure("chart crosshair scrub", async () => {
  for (let i = 0; i <= 120; i++) { await page.mouse.move(box.x + 70 + (box.w - 90) * (i / 120), box.y + box.h / 2); await sleep(12); }
  for (let i = 120; i >= 0; i--) { await page.mouse.move(box.x + 70 + (box.w - 90) * (i / 120), box.y + box.h / 3); await sleep(12); }
});

await measure("chart drag-to-compare", async () => {
  await page.mouse.move(box.x + 120, box.y + 120);
  await page.mouse.down();
  for (let i = 0; i <= 80; i++) { await page.mouse.move(box.x + 120 + (box.w - 260) * (i / 80), box.y + 120); await sleep(12); }
  await page.mouse.up();
  await sleep(700);
});

await measure("range switch ×6 (crossfade + domain ease)", async () => {
  for (const r of ["1G", "1H", "1A", "3A", "6A", "Tümü"]) { await clickText(".segmented button", r); await sleep(900); }
});

await measure("pan back/forward ×4", async () => {
  await clickText(".segmented button", "1A"); await sleep(800);
  for (const label of ["Önceki pencere", "Önceki pencere", "Sonraki pencere", "Sonraki pencere"]) { await click(`[aria-label="${label}"]`); await sleep(800); }
});

await measure("manual refresh (number tweens + data glide)", async () => {
  for (let i = 0; i < 3; i++) { await click('[aria-label="Yenile"]'); await sleep(1400); }
});

await measure("view switch ×8", async () => {
  for (const k of ["2", "3", "4", "1", "2", "3", "4", "1"]) { await page.keyboard.press(k); await sleep(650); }
});

await measure("theme toggle ×2", async () => {
  for (let i = 0; i < 2; i++) { await page.evaluate(() => document.querySelector('.topbar-actions .icon-btn[aria-label*="temaya"]').click()); await sleep(900); }
});

await page.keyboard.press("2"); await sleep(900);
await measure("positions sort ×4 (FLIP rows) + card/table toggle", async () => {
  for (const col of ["Enstrüman", "K/Z ₺", "Toplam get.", "Değer ₺"]) { await page.evaluate((c) => [...document.querySelectorAll(".th-btn")].find((b) => b.textContent.trim().startsWith(c))?.click(), col); await sleep(650); }
  await click('[aria-label="Kartlar"]'); await sleep(900);
  await click('[aria-label="Tablo"]'); await sleep(900);
});

await page.keyboard.press("3"); await sleep(900);
await measure("transaction sheet open/close + group collapse", async () => {
  await clickText(".head-actions .btn", "Yeni işlem"); await sleep(800);
  await page.keyboard.press("Escape"); await sleep(700);
  await page.evaluate(() => document.querySelector(".txn-group-head")?.click()); await sleep(700);
  await page.evaluate(() => document.querySelector(".txn-group-head")?.click()); await sleep(700);
});

await measure("command palette open/type/close", async () => {
  await page.keyboard.down("Control"); await page.keyboard.press("k"); await page.keyboard.up("Control");
  await sleep(400);
  await page.keyboard.type("aa", { delay: 120 });
  await page.keyboard.press("ArrowDown"); await sleep(200);
  await page.keyboard.press("Escape"); await sleep(500);
});

console.log(`\n== ${MOBILE ? "mobile 375×812 @2x" : "desktop 1440×900"} · CPU throttle ${THROTTLE}× ==`);
console.table(results);
await browser.close();
