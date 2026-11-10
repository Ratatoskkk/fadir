// Tax page: pick a Tax Jurisdiction and year, and the estimate loads for all of the
// User's Portfolios together, in that jurisdiction's currency.

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../../api.js";
import { fullDate, money, pct } from "../../format.js";
import { browserRegion, useI18n } from "../i18n/index.jsx";
import Icon from "../ui/Icons.jsx";
import { fadeUp, spring, stagger } from "../ui/motion.js";

const KEY = "fadir.tax";
const REGION_ALIAS = { UK: "GB" };

function remembered() {
  try { return JSON.parse(localStorage.getItem(KEY)) ?? {}; } catch { return {}; }
}

function remember(value) {
  try { localStorage.setItem(KEY, JSON.stringify(value)); } catch { /* private mode */ }
}

const rate = (value) => (value == null ? "—" : pct(Number(value) * 100).replace(/^[+]/, ""));

export default function TaxView({ dash, onSignIn }) {
  const { t, lang } = useI18n();
  const signedIn = dash.identityReady;
  const [jurisdictions, setJurisdictions] = useState([]);
  const [choice, setChoice] = useState(remembered);
  const [estimate, setEstimate] = useState(null);
  const [status, setStatus] = useState("idle");
  const [attempt, setAttempt] = useState(0);

  const regionName = useMemo(() => {
    try {
      const names = new Intl.DisplayNames([lang], { type: "region" });
      return (code) => names.of(code) ?? code;
    } catch {
      return (code) => code;
    }
  }, [lang]);

  useEffect(() => {
    api.taxJurisdictions().then((list) => setJurisdictions(Array.isArray(list) ? list : [])).catch(() => setStatus("error"));
  }, []);

  // Default to the remembered profile, else the viewer's region, else Turkey.
  const current = useMemo(() => {
    if (!jurisdictions.length) return null;
    const region = browserRegion();
    const code = [choice.jurisdiction, REGION_ALIAS[region] ?? region, "TR"].find((c) => jurisdictions.some((j) => j.code === c));
    const j = jurisdictions.find((x) => x.code === code);
    const thisYear = new Date().getFullYear();
    const year = j.years.includes(Number(choice.year)) ? Number(choice.year) : (j.years.includes(thisYear) ? thisYear : j.years[j.years.length - 1]);
    return { ...j, year };
  }, [jurisdictions, choice]);

  useEffect(() => {
    if (!current || !signedIn) return undefined;
    let live = true;
    setStatus("loading");
    api.taxEstimateFor(current.code, current.year)
      .then((value) => { if (live) { setEstimate(value); setStatus("ready"); } })
      .catch((err) => { if (live) { setEstimate(null); setStatus(err?.status === 503 ? "rates" : "error"); } });
    return () => { live = false; };
  }, [current?.code, current?.year, signedIn, attempt]); // eslint-disable-line react-hooks/exhaustive-deps

  function pick(next) {
    const value = { ...choice, ...next };
    setChoice(value);
    remember(value);
  }

  const yearLabel = (j, y) => (j.code === "GB" ? `${y}/${String(y + 1).slice(2)}` : String(y));
  const ccy = estimate?.currency;
  const cells = estimate ? [
    [t("tax.taxable"), money(estimate.taxable_gain, ccy)],
    [t("tax.realized"), money(estimate.gross_gain, ccy)],
    [t("tax.effective"), rate(estimate.effective_rate)],
    [t("tax.marginal"), rate(estimate.marginal_rate)],
    [t("tax.afterTax"), money(estimate.net_after_tax, ccy)],
  ] : [];

  return (
    <motion.div className="stack" variants={stagger(0.06)} initial="hidden" animate="show">
      <motion.section variants={fadeUp} className="card tax-page" aria-labelledby="tax-title">
        <header className="card-head">
          <div className="card-icon"><Icon name="receipt" /></div>
          <h2 id="tax-title">{t("nav.tax")}</h2>
        </header>

        {current && (
          <div className="tax-pickers">
            <div className="seg tax-countries" role="radiogroup" aria-label={t("tax.jurisdiction")}>
              {jurisdictions.map((j) => {
                const on = j.code === current.code;
                return (
                  <button key={j.code} type="button" role="radio" aria-checked={on} className={on ? "on" : ""} onClick={() => pick({ jurisdiction: j.code })}>
                    {on && <motion.span layoutId="tax-country" className="seg-pill" transition={spring} />}
                    <span className="seg-code">{j.code}</span>
                    <span className="seg-label">{regionName(j.code)}</span>
                  </button>
                );
              })}
            </div>
            <div className="seg tax-years" role="radiogroup" aria-label={t("tax.year")}>
              {current.years.map((y) => {
                const on = y === current.year;
                return (
                  <button key={y} type="button" role="radio" aria-checked={on} className={on ? "on" : ""} onClick={() => pick({ year: y })}>
                    {on && <motion.span layoutId="tax-year" className="seg-pill" transition={spring} />}
                    <span>{yearLabel(current, y)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {!signedIn && (
          <div className="tax-signin">
            <p className="muted">{t("tax.needsUser")}</p>
            {onSignIn && <button type="button" className="btn primary" onClick={onSignIn}>{t("identity.continue")}</button>}
          </div>
        )}
        {signedIn && status === "loading" && <div className="skeleton-grid" role="status" aria-label={t("common.loading")}>{Array.from({ length: 6 }, (_, i) => <i key={i} />)}</div>}
        {signedIn && (status === "rates" || status === "error") && (
          <div className="tax-error" role="alert">
            <p>{t(status === "rates" ? "tax.ratesUnavailable" : "tax.loadFailed")}</p>
            <button type="button" className="btn small" onClick={() => setAttempt((n) => n + 1)}>
              <Icon name="refresh" size={14} /> {t("common.retry")}
            </button>
          </div>
        )}

        <AnimatePresence mode="wait">
          {signedIn && status === "ready" && estimate && (
            <motion.div key={`${estimate.jurisdiction}-${estimate.tax_year}`} variants={stagger(0.04)} initial="hidden" animate="show" exit={{ opacity: 0 }}>
              <motion.div variants={fadeUp} className="tax-hero">
                <span className="label">{t("tax.estimated")}</span>
                <strong className="num">{money(estimate.tax, ccy)}</strong>
                <span className="muted num">{fullDate(estimate.period_start)} – {fullDate(estimate.period_end)}</span>
              </motion.div>
              <dl className="tax-grid">
                {cells.map(([k, v]) => (
                  <motion.div key={k} variants={fadeUp}><dt>{k}</dt><dd className="num">{v}</dd></motion.div>
                ))}
              </dl>
              {estimate.assumptions.length > 0 && (
                <motion.ul variants={fadeUp} className="assumptions">
                  {estimate.assumptions.map((key) => <li key={key}>{t(`tax.a.${key}`)}</li>)}
                </motion.ul>
              )}
              <motion.p variants={fadeUp} className="fineprint">
                {t("tax.source")}{" "}
                {/^https:\/\//.test(estimate.source_url)
                  ? <a href={estimate.source_url} target="_blank" rel="noreferrer">{estimate.source_version}</a>
                  : estimate.source_version}
              </motion.p>
              <motion.p variants={fadeUp} className="fineprint warn-text">{t("tax.disclaimer")}</motion.p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.section>
    </motion.div>
  );
}
