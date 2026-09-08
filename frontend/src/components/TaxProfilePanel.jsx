import { useEffect, useState } from "react";
import { api } from "../api.js";
import { money, pct } from "../format.js";

const CURRENT_YEAR = String(new Date().getFullYear());

function safeText(value) {
  return typeof value === "string" ? value : "";
}

function isSafeSourceUrl(value) {
  return /^https?:\/\//i.test(value);
}

function profileView(value) {
  if (!value || typeof value !== "object") return null;
  return {
    taxYear: safeText(value.tax_year),
    jurisdiction: safeText(value.jurisdiction),
    currency: safeText(value.currency) || "TRY",
    sourceUrl: safeText(value.source_url),
    sourceVersion: safeText(value.source_version),
    assumptions: Array.isArray(value.assumptions) ? value.assumptions.filter((item) => typeof item === "string") : [],
    disclaimer: safeText(value.disclaimer),
  };
}

function estimateView(value) {
  if (!value || typeof value !== "object") return null;
  return {
    taxYear: safeText(value.tax_year),
    jurisdiction: safeText(value.jurisdiction),
    sourceUrl: safeText(value.source_url),
    sourceVersion: safeText(value.source_version),
    tax: value.tax_try ?? value.tax,
    taxableGain: value.taxable_gain_try,
    grossGain: value.gross_gain_try,
    netAfterTax: value.net_after_tax_try,
    effectiveRate: value.effective_rate,
    marginalRate: value.marginal_rate,
  };
}

export default function TaxProfilePanel({ identityReady }) {
  const [year, setYear] = useState(CURRENT_YEAR);
  const [loadedYear, setLoadedYear] = useState(CURRENT_YEAR);
  const [profile, setProfile] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!identityReady) {
      setProfile(null);
      setEstimate(null);
      setStatus("idle");
      setError(null);
      return undefined;
    }

    let active = true;
    setStatus("loading");
    setError(null);
    setProfile(null);
    setEstimate(null);
    Promise.all([api.taxProfile(loadedYear), api.taxEstimate(loadedYear)])
      .then(([profileResponse, estimateResponse]) => {
        if (!active) return;
        setProfile(profileView(profileResponse));
        setEstimate(estimateView(estimateResponse));
        setStatus("ready");
      })
      .catch((err) => {
        if (!active) return;
        const message = String(err?.message ?? "");
        setError(message.startsWith("403")
          ? "Vergi profili yalnızca User Workspace için kullanılabilir."
          : "Vergi bilgisi yüklenemedi. Lütfen daha sonra tekrar deneyin.");
        setStatus("error");
      });
    return () => {
      active = false;
    };
  }, [identityReady, loadedYear]);

  function submit(event) {
    event.preventDefault();
    const parsed = Number(year);
    if (!Number.isInteger(parsed) || parsed < 2000 || parsed > 2100) {
      setError("2000–2100 arasında geçerli bir vergi yılı seçin.");
      setStatus("error");
      return;
    }
    setLoadedYear(String(parsed));
  }

  return (
    <section className="panel tax-profile-panel" aria-labelledby="tax-profile-title">
      <div className="panel-head">
        <h2 id="tax-profile-title">Vergi profili ve tahmini</h2>
        <span className="panel-sub">Gerçekleşen FIFO satışları için yayınlanmış kaynak</span>
      </div>
      <div className="panel-body">
        <form className="tax-year-form" onSubmit={submit}>
          <div className="field">
            <label htmlFor="tax-year">Vergi yılı</label>
            <input id="tax-year" type="number" min="2000" max="2100" value={year} onChange={(event) => setYear(event.target.value)} />
          </div>
          <button className="btn primary" type="submit" disabled={!identityReady || status === "loading"}>
            Vergi profilini yükle
          </button>
        </form>

        {!identityReady && <p className="hint" role="status">Vergi profili, Google kimlik geçişi tamamlandıktan sonra User Workspace için yüklenir.</p>}
        {status === "loading" && <p className="hint" role="status" aria-live="polite"><span className="spinner" /> Vergi bilgileri yükleniyor…</p>}
        {error && <div className="form-error" role="alert">{error}</div>}

        {status === "ready" && profile && estimate && (
          <div className="tax-profile-details">
            <div className="tax-profile-meta">
              <span><strong>Yıl</strong> {profile.taxYear || estimate.taxYear || loadedYear}</span>
              <span><strong>Yargı alanı</strong> {profile.jurisdiction || estimate.jurisdiction || "TR"}</span>
              <span><strong>Para birimi</strong> {profile.currency}</span>
              <span><strong>Kaynak sürümü</strong> {profile.sourceVersion || estimate.sourceVersion || "—"}</span>
            </div>
            <dl className="tax-profile-estimate">
              <div><dt>Tahmini vergi</dt><dd>{money(estimate.tax, profile.currency)}</dd></div>
              <div><dt>Vergiye tabi kazanç</dt><dd>{money(estimate.taxableGain, profile.currency)}</dd></div>
              <div><dt>Gerçekleşen kazanç</dt><dd>{money(estimate.grossGain, profile.currency)}</dd></div>
              <div><dt>Efektif oran</dt><dd>{estimate.effectiveRate == null ? "—" : pct(Number(estimate.effectiveRate) * 100)}</dd></div>
              <div><dt>Marjinal oran</dt><dd>{estimate.marginalRate == null ? "—" : pct(Number(estimate.marginalRate) * 100)}</dd></div>
              <div><dt>Vergi sonrası</dt><dd>{money(estimate.netAfterTax, profile.currency)}</dd></div>
            </dl>
            {profile.sourceUrl && <p className="tax-profile-source"><strong>Kaynak</strong>{" "}{isSafeSourceUrl(profile.sourceUrl) ? <a href={profile.sourceUrl} target="_blank" rel="noreferrer">{profile.sourceUrl}</a> : <span>{profile.sourceUrl}</span>}</p>}
            {profile.assumptions.length > 0 && <div className="tax-profile-assumptions"><strong>Varsayımlar</strong><ul>{profile.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></div>}
            {profile.disclaimer && <p className="tax-profile-disclaimer"><strong>Uyarı</strong> {profile.disclaimer}</p>}
          </div>
        )}
      </div>
    </section>
  );
}
