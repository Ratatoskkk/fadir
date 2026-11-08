// A further Portfolio in this Workspace: a name and a Base Currency. It gets its own code.

import { useState } from "react";
import { api } from "../../api.js";
import Dialog from "../ui/Dialog.jsx";
import { useToast } from "../ui/overlays.jsx";
import { useT } from "../i18n/index.jsx";

const CURRENCIES = ["TRY", "USD", "EUR", "GBP"];

export default function NewPortfolio({ open, onClose, dash }) {
  const t = useT();
  const toast = useToast();
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("TRY");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function close() {
    setName("");
    setError(null);
    onClose();
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createPortfolio({ name: name.trim(), base_currency: currency });
      await dash.loadAll();
      await dash.selectPortfolio(Number(created.id));
      toast({ tone: "up", text: t("portfolio.created", { name: created.name, code: created.code }) });
      close();
    } catch (err) {
      setError(err?.status === 409 ? t("portfolio.nameTaken") : err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={close} title={t("portfolio.new")}>
      <form className="txn-form" onSubmit={submit}>
        <div className="field">
          <label htmlFor="np-name">{t("portfolio.name")}</label>
          <input id="np-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={128} required autoFocus />
        </div>
        <div className="field">
          <label htmlFor="np-ccy">{t("portfolio.currency")}</label>
          <select id="np-ccy" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="btn primary" type="submit" disabled={busy || !name.trim()}>
          {busy ? <span className="spinner" /> : t("portfolio.create")}
        </button>
      </form>
    </Dialog>
  );
}
