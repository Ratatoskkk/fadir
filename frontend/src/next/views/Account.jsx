import { useState } from "react";
import { motion } from "framer-motion";
import { api } from "../../api.js";
import { switchUi } from "../../ui.js";
import Identity from "../components/Identity.jsx";
import Icon from "../ui/Icons.jsx";
import { copyCode } from "../ui/copy.js";
import { fadeUp, stagger } from "../ui/motion.js";
import { useConfirm, useToast } from "../ui/overlays.jsx";
import { LANGUAGES, useI18n, useT } from "../i18n/index.jsx";


function startDownload({ blob, filename }) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function DataRights({ dash }) {
  const { identityReady, selectedPortfolioId, portfolios, loadAll, clearAfterAccountDeletion } = dash;
  const [busy, setBusy] = useState(false);
  const confirm = useConfirm();
  const toast = useToast();
  const t = useT();
  const failed = () => toast({ tone: "down", text: t("common.failed") });

  async function exportPortfolio(format) {
    if (!identityReady || selectedPortfolioId === null) return;
    setBusy(true);
    try {
      startDownload(await api.exportPortfolio(selectedPortfolioId, format));
      toast({ tone: "up", text: t("rights.downloaded", { format: format.toUpperCase() }) });
    } catch {
      failed();
    } finally {
      setBusy(false);
    }
  }

  async function deletePortfolio() {
    if (!identityReady || selectedPortfolioId === null) return;
    const name = portfolios.find((p) => Number(p.id) === Number(selectedPortfolioId))?.name ?? "";
    const ok = await confirm({ title: t("rights.deletePortfolioTitle", { name }), body: t("common.irreversible"), confirmLabel: t("rights.deletePortfolio"), danger: true });
    if (!ok) return;
    setBusy(true);
    try {
      await api.deletePortfolio(selectedPortfolioId);
      toast({ tone: "info", text: t("rights.portfolioDeleted") });
      await loadAll();
    } catch {
      failed();
    } finally {
      setBusy(false);
    }
  }

  async function deleteAccount() {
    if (!identityReady) return;
    const ok = await confirm({ title: t("rights.deleteAccountTitle"), body: t("rights.deleteAccountBody"), confirmLabel: t("rights.deleteAccount"), danger: true });
    if (!ok) return;
    setBusy(true);
    try {
      await api.deleteAccount();
      clearAfterAccountDeletion();
      toast({ tone: "info", text: t("rights.accountDeleted") });
    } catch {
      failed();
    } finally {
      setBusy(false);
    }
  }

  if (!identityReady) return null;
  return (
    <section className="card" aria-labelledby="rights-title">
      <header className="card-head">
        <div className="card-icon"><Icon name="download" /></div>
        <h2 id="rights-title">{t("rights.title")}</h2>
      </header>
      <div className="rights-row">
        <div>
          <strong>{t("rights.selected")}</strong>
          <p className="muted">{t("rights.exportHint")}</p>
        </div>
        <div className="btn-row">
          <button className="btn" type="button" onClick={() => exportPortfolio("csv")} disabled={busy || selectedPortfolioId === null}>CSV</button>
          <button className="btn" type="button" onClick={() => exportPortfolio("json")} disabled={busy || selectedPortfolioId === null}>JSON</button>
          <button className="btn danger" type="button" onClick={deletePortfolio} disabled={busy || selectedPortfolioId === null}>{t("rights.deletePortfolio")}</button>
        </div>
      </div>
      <div className="rights-row danger-zone">
        <div>
          <strong>{t("rights.account")}</strong>
          <p className="muted">{t("rights.accountHint")}</p>
        </div>
        <button className="btn danger" type="button" onClick={deleteAccount} disabled={busy}>{t("rights.deleteAccount")}</button>
      </div>
    </section>
  );
}

function PortfolioCode({ dash, access, onLeave }) {
  const [shown, setShown] = useState(false);
  const { portfolios, selectedPortfolioId, renewCode } = dash;
  const [busy, setBusy] = useState(false);
  const confirm = useConfirm();
  const toast = useToast();
  const t = useT();
  const current = portfolios.find((p) => Number(p.id) === Number(selectedPortfolioId));
  if (!current?.code) return null;

  async function renew() {
    const ok = await confirm({
      title: t("code.renewTitle"),
      body: t("code.renewBody"),
      confirmLabel: t("code.renew"),
    });
    if (!ok) return;
    setBusy(true);
    try {
      await renewCode(current.id);
      toast({ tone: "up", text: t("code.renewed") });
    } catch {
      toast({ tone: "down", text: t("common.failed") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby="code-title">
      <header className="card-head">
        <div className="card-icon"><Icon name="key" /></div>
        <h2 id="code-title">{t("code.title")}</h2>
      </header>
      <div className="code-card-row">
        {shown
          ? <span className="code-big" aria-label={`${t("code.short")} ${current.code.split("").join(" ")}`}>{current.code}</span>
          : <span className="code-big code-hidden" aria-label={t("code.hidden")}>{"•".repeat(current.code.length)}</span>}
        <div className="btn-row">
          <button className="btn" type="button" aria-pressed={shown} onClick={() => setShown((v) => !v)}>
            <Icon name={shown ? "eyeOff" : "eye"} size={15} /> {t(shown ? "code.hide" : "code.show")}
          </button>
          <button className="btn" type="button" onClick={() => copyCode(current.code, toast, t)}><Icon name="copy" size={15} /> {t("code.copy")}</button>
          {access === "code" ? (
            <button className="btn" type="button" onClick={onLeave}><Icon name="x" size={15} /> {t("code.leave")}</button>
          ) : (
            <button className="btn" type="button" onClick={renew} disabled={busy}><Icon name="refresh" size={15} /> {t("code.renew")}</button>
          )}
        </div>
      </div>
    </section>
  );
}

function Preferences() {
  const { t, lang, setLang } = useI18n();
  return (
    <section className="card">
      <header className="card-head">
        <div className="card-icon"><Icon name="globe" /></div>
        <h2>{t("ui.title")}</h2>
      </header>
      <div className="rights-row">
        <strong>{t("ui.language")}</strong>
        <div className="seg" role="radiogroup" aria-label={t("ui.language")}>
          {LANGUAGES.map((l) => (
            <button key={l.code} type="button" role="radio" lang={l.code} aria-checked={lang === l.code} className={lang === l.code ? "on" : ""} onClick={() => setLang(l.code)}>
              {lang === l.code && <motion.span layoutId="lang-pill" className="seg-pill" />}
              <span>{l.label}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="rights-row">
        <strong>{t("ui.classicTitle")}</strong>
        <button className="btn" type="button" onClick={() => switchUi("classic")}>{t("ui.classic")}</button>
      </div>
    </section>
  );
}

export default function Account({ dash, access, onLeave, onSignOut }) {
  const t = useT();
  const owner = access !== "code";
  return (
    <motion.div className="stack" variants={stagger(0.08)} initial="hidden" animate="show">
      <motion.div variants={fadeUp}><PortfolioCode dash={dash} access={access} onLeave={onLeave} /></motion.div>
      {owner && <motion.div variants={fadeUp}><Identity onCompleted={dash.refreshAfterIdentity} onSignOut={onSignOut} /></motion.div>}
      {owner && <motion.div variants={fadeUp}><DataRights dash={dash} /></motion.div>}
      <motion.div variants={fadeUp}><Preferences /></motion.div>
      <motion.footer variants={fadeUp} className="legal" aria-label={t("legal.title")}>
        <span>{t("legal.privacy")}</span>
        <span>{t("legal.terms")}</span>
        <span>{t("legal.tax")}</span>
        <span>{t("legal.data")}</span>
        <span>{t("legal.guest")}</span>
      </motion.footer>
    </motion.div>
  );
}
