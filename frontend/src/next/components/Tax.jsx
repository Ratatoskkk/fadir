import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../../api.js";
import { money, pct } from "../../format.js";
import Icon from "../ui/Icons.jsx";
import { collapse, fadeUp, stagger } from "../ui/motion.js";

const CURRENT_YEAR = String(new Date().getFullYear());
const safeText = (v) => (typeof v === "string" ? v : "");
const isSafeSourceUrl = (v) => /^https?:\/\//i.test(v);

function profileView(v) {
  if (!v || typeof v !== "object") return null;
  return {
    taxYear: safeText(v.tax_year), jurisdiction: safeText(v.jurisdiction), currency: safeText(v.currency) || "TRY",
    sourceUrl: safeText(v.source_url), sourceVersion: safeText(v.source_version),
    assumptions: Array.isArray(v.assumptions) ? v.assumptions.filter((i) => typeof i === "string") : [],
    disclaimer: safeText(v.disclaimer),
  };
}

function estimateView(v) {
  if (!v || typeof v !== "object") return null;
  return {
    taxYear: safeText(v.tax_year), jurisdiction: safeText(v.jurisdiction), sourceVersion: safeText(v.source_version),
    tax: v.tax_try ?? v.tax, taxableGain: v.taxable_gain_try, grossGain: v.gross_gain_try, netAfterTax: v.net_after_tax_try,
    effectiveRate: v.effective_rate, marginalRate: v.marginal_rate,
  };
}

export default function Tax({ identityReady }) {
  const [year, setYear] = useState(CURRENT_YEAR);
  const [loadedYear, setLoadedYear] = useState(CURRENT_YEAR);
  const [profile, setProfile] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!identityReady) {
      setProfile(null); setEstimate(null); setStatus("idle"); setError(null);
      return undefined;
    }
    let active = true;
    setStatus("loading"); setError(null); setProfile(null); setEstimate(null);
    Promise.all([api.taxProfile(loadedYear), api.taxEstimate(loadedYear)])
      .then(([p, e]) => {
        if (!active) return;
        setProfile(profileView(p));
        setEstimate(estimateView(e));
        setStatus("ready");
      })
      .catch((err) => {
        if (!active) return;
        if (err?.status === 404) { setStatus("missing"); return; }
        setError(String(err?.message ?? "").startsWith("403")
          ? "Vergi profili yalnızca User Workspace için kullanılabilir."
          : "Vergi bilgisi yüklenemedi. Lütfen daha sonra tekrar deneyin.");
        setStatus("error");
      });
    return () => { active = false; };
  }, [identityReady, loadedYear]);

  function submit(e) {
    e.preventDefault();
    const parsed = Number(year);
    if (!Number.isInteger(parsed) || parsed < 2000 || parsed > 2100) {
      setError("2000–2100 arasında geçerli bir vergi yılı seçin.");
      setStatus("error");
      return;
    }
    setLoadedYear(String(parsed));
  }

  const cells = estimate && profile ? [
    ["Tahmini vergi", money(estimate.tax, profile.currency)],
    ["Vergiye tabi kazanç", money(estimate.taxableGain, profile.currency)],
    ["Gerçekleşen kazanç", money(estimate.grossGain, profile.currency)],
    ["Efektif oran", estimate.effectiveRate == null ? "—" : pct(Number(estimate.effectiveRate) * 100)],
    ["Marjinal oran", estimate.marginalRate == null ? "—" : pct(Number(estimate.marginalRate) * 100)],
    ["Vergi sonrası", money(estimate.netAfterTax, profile.currency)],
  ] : [];

  return (
    <section className="card" aria-labelledby="tax-title">
      <header className="card-head">
        <div className="card-icon"><Icon name="receipt" /></div>
        <h2 id="tax-title">Vergi profili</h2>
        <form className="year-form" onSubmit={submit}>
          <label htmlFor="tax-year" className="sr-only">Vergi yılı</label>
          <input id="tax-year" type="number" min="2000" max="2100" value={year} onChange={(e) => setYear(e.target.value)} />
          <button className="btn" type="submit" disabled={!identityReady || status === "loading"}>Yükle</button>
        </form>
      </header>

      {!identityReady && <p className="muted" role="status">Google kimlik geçişinden sonra User Workspace için yüklenir.</p>}
      {status === "loading" && <div className="skeleton-grid" role="status" aria-label="Vergi bilgileri yükleniyor">{Array.from({ length: 6 }, (_, i) => <i key={i} />)}</div>}
      {status === "missing" && <p className="muted" role="status">{loadedYear} için resmi vergi tarifesi yok.</p>}
      <AnimatePresence>{error && <motion.div className="form-error" role="alert" {...collapse}><div>{error}</div></motion.div>}</AnimatePresence>

      {status === "ready" && profile && estimate && (
        <motion.div variants={stagger(0.05)} initial="hidden" animate="show">
          <motion.div variants={fadeUp} className="tax-meta">
            <span><b>Yıl</b> {profile.taxYear || estimate.taxYear || loadedYear}</span>
            <span><b>Yargı alanı</b> {profile.jurisdiction || estimate.jurisdiction || "TR"}</span>
            <span><b>Para birimi</b> {profile.currency}</span>
            <span><b>Kaynak sürümü</b> {profile.sourceVersion || estimate.sourceVersion || "—"}</span>
          </motion.div>
          <dl className="tax-grid">
            {cells.map(([k, v]) => (
              <motion.div key={k} variants={fadeUp}><dt>{k}</dt><dd className="num">{v}</dd></motion.div>
            ))}
          </dl>
          {profile.sourceUrl && (
            <motion.p variants={fadeUp} className="fineprint">
              Kaynak:{" "}
              {isSafeSourceUrl(profile.sourceUrl)
                ? <a href={profile.sourceUrl} target="_blank" rel="noreferrer">{profile.sourceUrl}</a>
                : <span>{profile.sourceUrl}</span>}
            </motion.p>
          )}
          {profile.assumptions.length > 0 && (
            <motion.ul variants={fadeUp} className="assumptions">{profile.assumptions.map((a) => <li key={a}>{a}</li>)}</motion.ul>
          )}
          {profile.disclaimer && <motion.p variants={fadeUp} className="fineprint warn-text">{profile.disclaimer}</motion.p>}
        </motion.div>
      )}
    </section>
  );
}
