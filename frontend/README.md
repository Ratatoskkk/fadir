# faðir frontend

Two interfaces ship in one bundle. Each is a lazy chunk, so a browser downloads only the one it runs.

| Interface | Code | Stack |
|---|---|---|
| **next** (default) | `src/next/` | React 18, Framer Motion, hand-written canvas chart |
| **classic** | `src/classic/` | The original UI, unchanged apart from import paths and a "yeni arayüz" button |

Both share `src/api.js`, `src/format.js`, `src/ranges.js`, `src/flash.js` and `src/google.js`. `src/main.jsx` picks the interface through `src/ui.js`.

## Reverting to the classic interface

Pick the scope you need:

| Scope | How |
|---|---|
| One browser | **Hesap → Arayüz → Klasik arayüz**, the command palette (`Ctrl K` → "Klasik"), or open `/?ui=classic`. The choice is stored in `localStorage` (`fadir.ui`). `/?ui=next` or the classic UI's "yeni arayüz" button switches back. |
| Every visitor by default | `npm run build:classic`. This builds with `VITE_UI=classic` from `.env.classic`. A browser that saved its own choice keeps it. |
| Code | `git checkout classic-frontend-v1 -- frontend` restores the frontend exactly as it was before the rebuild. |

## Development

```bash
npm install
npm run dev:mock   # http://localhost:5173 on a synthetic in-memory API, no backend needed
npm run dev        # proxies /api to the FastAPI app on 127.0.0.1:8000
npm run build      # production bundle in dist/, served by the FastAPI app
```

`dev:mock` exists because the real server only accepts requests whose `Origin` is the hosted domain, so a local browser cannot get past guest bootstrap. The mock (`mock/mockApi.js`) holds synthetic data only, random-walks prices on every read, and derives positions from its transactions, so adding or deleting a trade changes the dashboard. It runs in the dev server only and never reaches a build. Add `?synthetic-google` to the URL to step through the Google identity flow.

## The next interface

- **Routes**: hash routes `#/genel`, `#/pozisyonlar`, `#/islemler` and `#/hesap`, so deep links and the back button work.
- **Data**: `src/next/useDashboard.js` owns all loading, polling and actions, ported from the classic App. The poll runs fast while a market is open and falls back to every 15 minutes while only FX moves. It skips ticks while the tab is hidden and refreshes on return.
- **Chart**: `src/next/chart/ValueChart.jsx` draws on a canvas and runs `requestAnimationFrame` only while something is moving. Values, the y domain and series opacity ease toward their targets. A range change crossfades and slides in from the direction of travel. Drag across the chart to compare two points; the parts add up exactly to the change in value.
- **Motion rules**: continuous animation uses `transform` and `opacity` only. `backdrop-filter` appears only on the top bar, the bottom nav and modal scrims. Number tweens write `textContent` from rAF with no React renders. `prefers-reduced-motion` turns off tweens and ambient motion.
- **Keys**: `1`–`4` switch views, `N` opens a new transaction, `R` refreshes, `/` or `Ctrl K` opens the command palette.
- **Fonts**: Geologica is bundled through `@fontsource-variable` because the CSP blocks external font hosts. It draws a real ₺ and has tabular figures.
- **Style**: one flat ground, one cobalt accent mixed in OKLCH, and no glows, gradients or tilt. [docs/DESLOP.md](../docs/DESLOP.md) holds the rules every change is checked against.

Check frontend changes in a browser at desktop width and at 375px, in both themes.

## Frame-rate check

`bench/frames.mjs` drives 12 scenarios in headless Chrome against the production bundle and reports frame times: idle, scroll, chart scrub and drag, range and pan changes, refresh, view switches, theme toggle, sorting, the transaction sheet and the palette. Run it after changes that touch motion or rendering; the README header in the script has the commands.

The 2026-11-10 baseline, with every frame budgeted at 60fps (16.7ms):

| Profile | Frames on time | Worst frame |
|---|---|---|
| Desktop 1440×900 | ≥ 99.7% in every scenario, 100% in 11 of 12 | 29ms, once, on the first range switch |
| Phone 375×812 @2× | 100% in all 12 | 25ms, on the theme switch |
| Desktop, CPU slowed 4× | ≥ 92.7% | 79ms during the theme switch |

The script enters the mock API's synthetic Portfolio Code and pins Turkish, so its label selectors match.
