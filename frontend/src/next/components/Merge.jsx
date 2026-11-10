import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../../api.js";
import { fullDate, money } from "../../format.js";
import { collapse, ease } from "../ui/motion.js";
import { useT } from "../i18n/index.jsx";

const optionLabel = (o) => `${o.name} (${o.base_currency})`;
const transactionLabel = (x, t) =>
  `${fullDate(x.trade_date)}, ${t(x.side === "BUY" ? "txn.buy" : "txn.sell")}, ${money(x.price_native, x.currency)}`;

export default function Merge({ onCompleted }) {
  const t = useT();
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
      .catch((err) => active && setError(t("merge.optionsFailed", { error: err.message })))
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
      setError(t("merge.pickBoth"));
      return;
    }
    setBusy(true);
    try {
      setPreview(await api.mergePreview({ source_portfolio_id: Number(sourceId), target_portfolio_id: Number(targetId) }));
      setDecisions({});
    } catch (err) {
      setPreview(null);
      setError(t("merge.previewFailed", { error: err.message }));
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
        setError(t("merge.refreshFailed", { error: refreshError.message }));
      }
    } catch (err) {
      setError(t("merge.rejected", { error: err.message }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="merge" aria-labelledby="merge-title">
      <h3 id="merge-title">{t("merge.title")}</h3>
      <AnimatePresence>{error && <motion.div className="form-error" role="alert" {...collapse}><div>{error}</div></motion.div>}</AnimatePresence>
      {result && (
        <div className="success" role="status">
          {t("merge.done", { moved: result.moved_count, skipped: result.skipped_count })}
        </div>
      )}
      <form className="merge-form" onSubmit={showPreview}>
        <div className="field">
          <label htmlFor="merge-source">{t("merge.source")}</label>
          <select id="merge-source" value={sourceId} onChange={(e) => setSourceId(e.target.value)} disabled={busy || !options} required>
            <option value="">{t("common.choose")}</option>
            {(options?.source ?? []).map((o) => <option key={o.id} value={o.id}>{optionLabel(o)}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="merge-target">{t("merge.target")}</label>
          <select id="merge-target" value={targetId} onChange={(e) => setTargetId(e.target.value)} disabled={busy || !options} required>
            <option value="">{t("common.choose")}</option>
            {(options?.target ?? []).map((o) => <option key={o.id} value={o.id}>{optionLabel(o)}</option>)}
          </select>
        </div>
        <button className="btn primary" type="submit" disabled={busy || !options}>{busy ? t("common.preparing") : t("merge.preview")}</button>
      </form>

      <AnimatePresence>
        {preview && (
          <motion.div className="merge-preview" {...collapse}>
            <div>
              <p className="muted">{t("merge.summary", { movable: preview.movable_source_rows?.length ?? 0, duplicates: candidates.length })}</p>
              {candidates.map(({ source, target, differences }, i) => (
                <motion.fieldset
                  className="merge-candidate"
                  key={source.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0, transition: { delay: i * 0.05, ease } }}
                >
                  <legend>{t("merge.duplicate")}</legend>
                  <div className="merge-comparison">
                    <span>{t("merge.guestRow", { row: transactionLabel(source, t) })}</span>
                    <span>{t("merge.targetRow", { row: transactionLabel(target, t) })}</span>
                  </div>
                  {differences?.length > 0 && <p className="muted">{t("merge.differences", { fields: differences.map((d) => d.field).join(", ") })}</p>}
                  <div className="merge-decisions" role="radiogroup" aria-label={t("merge.decision", { id: source.id })}>
                    {[["keep", t("merge.keep")], ["skip", t("merge.skip")]].map(([value, label]) => (
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
                {busy ? t("common.confirming") : t("merge.confirm")}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
