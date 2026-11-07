// Find an instrument by ticker or name. Known instruments answer instantly; Yahoo
// fills in every other listed equity and ETF a moment later. The closest match is
// ghost-completed in the input and carries the highlight, which slides as you type.

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { api } from "../../api.js";
import { useT } from "../i18n/index.jsx";
import Icon from "../ui/Icons.jsx";
import { sound } from "../ui/sound.js";

const MAX_ROWS = 8;
const fold = (s) => (s ?? "").toLocaleUpperCase("en").normalize("NFD").replace(/\p{M}/gu, "");

/** Lower is closer: exact ticker, ticker prefix, word prefix in the name, then contains. */
function score(item, q) {
  const ticker = fold(item.ticker);
  const symbol = fold(item.yf_symbol);
  const name = fold(item.name);
  if (ticker === q || symbol === q) return 0;
  if (ticker.startsWith(q) || symbol.startsWith(q)) return 1 + (ticker.length - q.length) / 100;
  if (name.split(/[\s.,-]+/).some((word) => word.startsWith(q))) return 2;
  if (ticker.includes(q) || symbol.includes(q)) return 3;
  if (name.includes(q)) return 4;
  return null;
}

function rank(items, q) {
  return items
    .map((item, i) => ({ item, s: score(item, q), i }))
    .filter((r) => r.s !== null)
    .sort((a, b) => a.s - b.s || Number(b.item.known) - Number(a.item.known) || a.i - b.i)
    .map((r) => r.item);
}

function Highlight({ text, query }) {
  const at = fold(text).indexOf(query);
  if (!query || at < 0) return text;
  return <>{text.slice(0, at)}<mark>{text.slice(at, at + query.length)}</mark>{text.slice(at + query.length)}</>;
}

export default function TickerSearch({ instruments, onPick }) {
  const t = useT();
  const [text, setText] = useState("");
  const [remote, setRemote] = useState({ q: "", rows: [] });
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const q = fold(text.trim());

  useEffect(() => { inputRef.current?.focus(); }, []);

  // Yahoo search, debounced; a stale answer never replaces a newer one.
  useEffect(() => {
    if (!q) { setRemote({ q: "", rows: [] }); setLoading(false); return undefined; }
    setLoading(true);
    let live = true;
    const id = window.setTimeout(async () => {
      try {
        const rows = await api.searchInstruments(text.trim());
        if (live) setRemote({ q, rows: Array.isArray(rows) ? rows : [] });
      } catch {
        if (live) setRemote({ q, rows: [] });
      } finally {
        if (live) setLoading(false);
      }
    }, 180);
    return () => { live = false; window.clearTimeout(id); };
  }, [q, text]);

  const known = useMemo(
    () => instruments.map((i) => ({ yf_symbol: i.yf_symbol, ticker: i.ticker, name: i.name, exchange: i.exchange, currency: i.currency, known: true })),
    [instruments],
  );

  const rows = useMemo(() => {
    if (!q) return known.slice(0, MAX_ROWS);
    const seen = new Set();
    const merged = [];
    for (const item of [...known, ...remote.rows]) {
      const id = fold(item.yf_symbol);
      if (seen.has(id)) continue;
      seen.add(id);
      merged.push(item);
    }
    return rank(merged, q).slice(0, MAX_ROWS);
  }, [known, remote, q]);

  useEffect(() => { setActive(0); }, [q]);
  const current = rows[Math.min(active, rows.length - 1)];

  // Ghost completion: the rest of the closest ticker, drawn after what was typed.
  const best = rows[0];
  const ghost = q && best && fold(best.ticker).startsWith(q) && best.ticker.length > text.trim().length
    ? best.ticker.slice(text.trim().length)
    : "";

  function change(e) {
    const next = e.target.value.slice(0, 40);
    if (next.length > text.length) sound.key();
    else if (next.length < text.length) sound.erase();
    setText(next);
  }

  function pick(item) {
    if (!item) return;
    sound.pick();
    onPick(item);
  }

  function onKeyDown(e) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, rows.length - 1)); sound.key(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); sound.key(); }
    else if (e.key === "Enter") { e.preventDefault(); pick(current); }
    else if (e.key === "Tab" && ghost) { e.preventDefault(); setText(best.ticker); sound.key(); }
  }

  return (
    <div className="ticker-search">
      <label className="ticker-input">
        <Icon name="search" size={20} />
        <span className="ticker-field">
          <span className="ticker-ghost" aria-hidden="true"><span>{text}</span>{ghost}</span>
          <input
            ref={inputRef}
            value={text}
            onChange={change}
            onKeyDown={onKeyDown}
            placeholder={t("txn.searchPlaceholder")}
            aria-label={t("txn.instrument")}
            role="combobox"
            aria-expanded={rows.length > 0}
            aria-controls="ticker-results"
            aria-activedescendant={current ? `ticker-${current.yf_symbol}` : undefined}
            autoComplete="off"
            spellCheck={false}
          />
        </span>
        {loading && <span className="spinner" aria-hidden="true" />}
      </label>

      <LayoutGroup id="ticker-results">
        <ul id="ticker-results" className="ticker-results" role="listbox" aria-label={t("txn.instrument")}>
          <AnimatePresence initial={false} mode="popLayout">
            {rows.map((item, i) => {
              const on = item === current;
              return (
                <motion.li
                  key={item.yf_symbol}
                  id={`ticker-${item.yf_symbol}`}
                  layout="position"
                  role="option"
                  aria-selected={on}
                  className={`ticker-row ${on ? "on" : ""}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0, transition: { duration: 0.18, delay: Math.min(i, 5) * 0.02 } }}
                  exit={{ opacity: 0, transition: { duration: 0.1 } }}
                  transition={{ type: "spring", stiffness: 520, damping: 40 }}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => { e.preventDefault(); pick(item); }}
                >
                  {on && <motion.span layoutId="ticker-highlight" className="ticker-highlight" transition={{ type: "spring", stiffness: 600, damping: 42 }} />}
                  <span className="ticker-sym"><Highlight text={item.ticker} query={q} /></span>
                  <span className="ticker-name"><Highlight text={item.name} query={q} /></span>
                  <span className="ticker-meta">
                    {item.exchange}
                    {item.currency && <b>{item.currency}</b>}
                  </span>
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      </LayoutGroup>
      {q && !loading && rows.length === 0 && <p className="ticker-empty muted">{t("txn.noMatch")}</p>}
    </div>
  );
}
