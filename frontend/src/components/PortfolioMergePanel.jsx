import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { fullDate, money } from "../format.js";

function optionLabel(option) {
  return `${option.name} · ${option.base_currency}`;
}

function transactionLabel(transaction) {
  const side = transaction.side === "BUY" ? "alış" : "satış";
  return `${fullDate(transaction.trade_date)} · ${side} · ${money(
    transaction.price_native,
    transaction.currency,
  )}`;
}

export default function PortfolioMergePanel({ onCompleted }) {
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
      .then((value) => {
        if (active) setOptions(value);
      })
      .catch((err) => {
        if (active) setError(`Portföy seçenekleri alınamadı: ${err.message}`);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const candidates = preview?.candidates ?? [];
  const allDecided = useMemo(
    () => candidates.length === 0 || candidates.every(({ source }) => decisions[source.id]),
    [candidates, decisions],
  );

  async function showPreview(event) {
    event.preventDefault();
    setError(null);
    setResult(null);
    if (!sourceId || !targetId || sourceId === targetId) {
      setError("Kaynak ve hedef Portföyü açıkça seçin; aynı Portföy seçilemez.");
      return;
    }
    setBusy(true);
    try {
      const value = await api.mergePreview({
        source_portfolio_id: Number(sourceId),
        target_portfolio_id: Number(targetId),
      });
      setPreview(value);
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
        decisions: candidates.map(({ source }) => ({
          source_transaction_id: source.id,
          action: decisions[source.id],
        })),
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
    <section className="panel merge-panel" aria-labelledby="merge-title">
      <div className="panel-head">
        <h2 id="merge-title">Portföy birleştirme</h2>
        <span className="panel-sub">Misafir işlemlerini seçtiğiniz User Portföyüne taşıyın</span>
      </div>
      <div className="panel-body">
        {error && <div className="form-error" role="alert">{error}</div>}
        {result && (
          <div className="banner warn" role="status">
            Birleştirme tamamlandı: {result.moved_count} işlem taşındı, {result.skipped_count} işlem atlandı.
          </div>
        )}

        <form className="merge-form" onSubmit={showPreview}>
          <div className="field">
            <label htmlFor="merge-source">Kaynak Portföy</label>
            <select
              id="merge-source"
              value={sourceId}
              onChange={(event) => setSourceId(event.target.value)}
              disabled={busy || !options}
              required
            >
              <option value="">Seçin…</option>
              {(options?.source ?? []).map((option) => (
                <option key={option.id} value={option.id}>{optionLabel(option)}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="merge-target">Hedef Portföy</label>
            <select
              id="merge-target"
              value={targetId}
              onChange={(event) => setTargetId(event.target.value)}
              disabled={busy || !options}
              required
            >
              <option value="">Seçin…</option>
              {(options?.target ?? []).map((option) => (
                <option key={option.id} value={option.id}>{optionLabel(option)}</option>
              ))}
            </select>
          </div>
          <button className="btn primary" type="submit" disabled={busy || !options}>
            {busy ? "hazırlanıyor…" : "Önizlemeyi göster"}
          </button>
        </form>

        {preview && (
          <div className="merge-preview">
            <p className="hint">
              Önizleme: {preview.movable_source_rows?.length ?? 0} taşınabilir işlem, {candidates.length} olası yinelenen işlem.
            </p>
            {candidates.length > 0 ? (
              <div className="merge-candidates">
                {candidates.map(({ source, target, differences }) => (
                  <fieldset className="merge-candidate" key={source.id}>
                    <legend>Olası yinelenen işlem</legend>
                    <div className="merge-comparison">
                      <span>Misafir: {transactionLabel(source)}</span>
                      <span>Hedef: {transactionLabel(target)}</span>
                    </div>
                    {differences?.length > 0 && (
                      <p className="hint">Farklı alanlar: {differences.map((difference) => difference.field).join(", ")}</p>
                    )}
                    <div className="merge-decisions" role="radiogroup" aria-label={`İşlem ${source.id} kararı`}>
                      <label>
                        <input
                          type="radio"
                          name={`merge-decision-${source.id}`}
                          value="keep"
                          checked={decisions[source.id] === "keep"}
                          onChange={() => setDecisions((current) => ({ ...current, [source.id]: "keep" }))}
                        />
                        Tut
                      </label>
                      <label>
                        <input
                          type="radio"
                          name={`merge-decision-${source.id}`}
                          value="skip"
                          checked={decisions[source.id] === "skip"}
                          onChange={() => setDecisions((current) => ({ ...current, [source.id]: "skip" }))}
                        />
                        Atla
                      </label>
                    </div>
                  </fieldset>
                ))}
              </div>
            ) : (
              <p className="hint">Yinelenen işlem bulunmadı; önizlemeyi onaylayabilirsiniz.</p>
            )}
            <button className="btn primary" type="button" onClick={confirmMerge} disabled={busy || !allDecided}>
              {busy ? "onaylanıyor…" : "Birleştirmeyi onayla"}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
