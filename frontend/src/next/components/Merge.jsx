import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../../api.js";
import { fullDate, money } from "../../format.js";
import { collapse, ease } from "../ui/motion.js";

const optionLabel = (o) => `${o.name} · ${o.base_currency}`;
const transactionLabel = (t) =>
  `${fullDate(t.trade_date)} · ${t.side === "BUY" ? "alış" : "satış"} · ${money(t.price_native, t.currency)}`;

export default function Merge({ onCompleted }) {
  const [options, setOptions] = useState(null);
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [preview, setPreview] = useState(null);
  const [decisions, setDecisions] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    let active = true;
    setBusy(true);
    api.mergeOptions()
      .then((value) => active && setOptions(value))
      .catch((err) => active && setError(`Portföy seçenekleri alınamadı: ${err.message}`))
      .finally(() => active && setBusy(false));
    return () => { active = false; };
  }, []);

  const candidates = preview?.candidates ?? [];
  const allDecided = useMemo(
    () => candidates.length === 0 || candidates.every(({ source }) => decisions[source.id]),
    [candidates, decisions],
  );

  async function showPreview(e) {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!sourceId || !targetId || sourceId === targetId) {
      setError("Kaynak ve hedef Portföyü açıkça seçin; aynı Portföy seçilemez.");
      return;
    }
    setBusy(true);
    try {
      setPreview(await api.mergePreview({ source_portfolio_id: Number(sourceId), target_portfolio_id: Number(targetId) }));
      setDecisions({});
    } catch (err) {
      setPreview(null);
      setError(`Birleştirme önizlemesi alınamadı: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function confirmMerge() {
    if (!preview || !allDecided) return;
    setBusy(true);
    setError(null);
    try {
      const value = await api.mergeConfirm({
        source_portfolio_id: preview.source_portfolio_id,
        target_portfolio_id: preview.target_portfolio_id,
        revision_token: preview.revision_token,
        decisions: candidates.map(({ source }) => ({ source_transaction_id: source.id, action: decisions[source.id] })),
      });
      setResult(value);
      try {
        await onCompleted?.();
      } catch (refreshError) {
        setError(`Birleştirme tamamlandı; pano yenilenemedi: ${refreshError.message}`);
      }
    } catch (err) {
      setError(`Birleştirme reddedildi veya önizleme güncel değil: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="merge" aria-labelledby="merge-title">
      <h3 id="merge-title">Portföy birleştirme</h3>
      <AnimatePresence>{error && <motion.div className="form-error" role="alert" {...collapse}><div>{error}</div></motion.div>}</AnimatePresence>
      {result && (
        <div className="success" role="status">
          Birleştirme tamamlandı: {result.moved_count} işlem taşındı, {result.skipped_count} işlem atlandı.
        </div>
      )}
      <form className="merge-form" onSubmit={showPreview}>
        <div className="field">
          <label htmlFor="merge-source">Kaynak Portföy</label>
          <select id="merge-source" value={sourceId} onChange={(e) => setSourceId(e.target.value)} disabled={busy || !options} required>
            <option value="">Seçin…</option>
            {(options?.source ?? []).map((o) => <option key={o.id} value={o.id}>{optionLabel(o)}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="merge-target">Hedef Portföy</label>
          <select id="merge-target" value={targetId} onChange={(e) => setTargetId(e.target.value)} disabled={busy || !options} required>
            <option value="">Seçin…</option>
            {(options?.target ?? []).map((o) => <option key={o.id} value={o.id}>{optionLabel(o)}</option>)}
          </select>
        </div>
        <button className="btn primary" type="submit" disabled={busy || !options}>{busy ? "hazırlanıyor…" : "Önizlemeyi göster"}</button>
      </form>

      <AnimatePresence>
        {preview && (
          <motion.div className="merge-preview" {...collapse}>
            <div>
              <p className="muted">{preview.movable_source_rows?.length ?? 0} taşınabilir işlem, {candidates.length} olası yinelenen işlem.</p>
              {candidates.map(({ source, target, differences }, i) => (
                <motion.fieldset
                  className="merge-candidate"
                  key={source.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0, transition: { delay: i * 0.05, ease } }}
                >
                  <legend>Olası yinelenen işlem</legend>
                  <div className="merge-comparison">
                    <span>Misafir: {transactionLabel(source)}</span>
                    <span>Hedef: {transactionLabel(target)}</span>
                  </div>
                  {differences?.length > 0 && <p className="muted">Farklı alanlar: {differences.map((d) => d.field).join(", ")}</p>}
                  <div className="merge-decisions" role="radiogroup" aria-label={`İşlem ${source.id} kararı`}>
                    {[["keep", "Tut"], ["skip", "Atla"]].map(([value, label]) => (
                      <label key={value} className={decisions[source.id] === value ? "on" : ""}>
                        <input
                          type="radio"
                          name={`merge-decision-${source.id}`}
                          value={value}
                          checked={decisions[source.id] === value}
                          onChange={() => setDecisions((cur) => ({ ...cur, [source.id]: value }))}
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </motion.fieldset>
              ))}
              <button className="btn primary" type="button" onClick={confirmMerge} disabled={busy || !allDecided}>
                {busy ? "onaylanıyor…" : "Birleştirmeyi onayla"}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
