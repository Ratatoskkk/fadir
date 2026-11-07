import { useState } from "react";
import { motion } from "framer-motion";
import { api } from "../../api.js";
import { switchUi } from "../../ui.js";
import Identity from "../components/Identity.jsx";
import Tax from "../components/Tax.jsx";
import Icon from "../ui/Icons.jsx";
import { copyCode } from "../ui/copy.js";
import { fadeUp, stagger } from "../ui/motion.js";
import { useConfirm, useToast } from "../ui/overlays.jsx";

const GENERIC_RIGHTS_ERROR = "Bu işlem şu anda tamamlanamadı. Lütfen tekrar deneyin.";

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

  async function exportPortfolio(format) {
    if (!identityReady || selectedPortfolioId === null) return;
    setBusy(true);
    try {
      startDownload(await api.exportPortfolio(selectedPortfolioId, format));
      toast({ tone: "up", text: `${format.toUpperCase()} indirildi` });
    } catch {
      toast({ tone: "down", text: GENERIC_RIGHTS_ERROR });
    } finally {
      setBusy(false);
    }
  }

  async function deletePortfolio() {
    if (!identityReady || selectedPortfolioId === null) return;
    const name = portfolios.find((p) => Number(p.id) === Number(selectedPortfolioId))?.name ?? "bu Portföy";
    const ok = await confirm({ title: `“${name}” Portföyü silinsin mi?`, body: "Bu işlem geri alınamaz.", confirmLabel: "Portföyü sil", danger: true });
    if (!ok) return;
    setBusy(true);
    try {
      await api.deletePortfolio(selectedPortfolioId);
      toast({ tone: "info", text: "Portföy silindi." });
      await loadAll();
    } catch {
      toast({ tone: "down", text: GENERIC_RIGHTS_ERROR });
    } finally {
      setBusy(false);
    }
  }

  async function deleteAccount() {
    if (!identityReady) return;
    const ok = await confirm({ title: "User hesabı silinsin mi?", body: "Hesap ve bağlı tüm Portföyler kalıcı olarak silinir. Bu işlem geri alınamaz.", confirmLabel: "Hesabı sil", danger: true });
    if (!ok) return;
    setBusy(true);
    try {
      await api.deleteAccount();
      clearAfterAccountDeletion();
      toast({ tone: "info", text: "User verileri silindi." });
    } catch {
      toast({ tone: "down", text: GENERIC_RIGHTS_ERROR });
    } finally {
      setBusy(false);
    }
  }

  if (!identityReady) return null;
  return (
    <section className="card" aria-labelledby="rights-title">
      <header className="card-head">
        <div className="card-icon"><Icon name="download" /></div>
        <h2 id="rights-title">Veri hakları</h2>
      </header>
      <div className="rights-row">
        <div>
          <strong>Seçili Portföy</strong>
          <p className="muted">CSV veya JSON olarak indirin.</p>
        </div>
        <div className="btn-row">
          <button className="btn" type="button" onClick={() => exportPortfolio("csv")} disabled={busy || selectedPortfolioId === null}>CSV</button>
          <button className="btn" type="button" onClick={() => exportPortfolio("json")} disabled={busy || selectedPortfolioId === null}>JSON</button>
          <button className="btn danger" type="button" onClick={deletePortfolio} disabled={busy || selectedPortfolioId === null}>Portföyü sil</button>
        </div>
      </div>
      <div className="rights-row danger-zone">
        <div>
          <strong>User hesabı</strong>
          <p className="muted">Hesap ve bağlı Portföyler kalıcı olarak silinir.</p>
        </div>
        <button className="btn danger" type="button" onClick={deleteAccount} disabled={busy}>Hesabı sil</button>
      </div>
    </section>
  );
}

function PortfolioCode({ dash, access, onLeave }) {
  const { portfolios, selectedPortfolioId, renewCode } = dash;
  const [busy, setBusy] = useState(false);
  const confirm = useConfirm();
  const toast = useToast();
  const current = portfolios.find((p) => Number(p.id) === Number(selectedPortfolioId));
  if (!current?.code) return null;

  async function renew() {
    const ok = await confirm({
      title: "Yeni kod oluşturulsun mu?",
      body: "Eski kodla açılan diğer cihazlarda Portföy kapanır.",
      confirmLabel: "Yeni kod",
    });
    if (!ok) return;
    setBusy(true);
    try {
      await renewCode(current.id);
      toast({ tone: "up", text: "Yeni kod hazır" });
    } catch {
      toast({ tone: "down", text: GENERIC_RIGHTS_ERROR });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby="code-title">
      <header className="card-head">
        <div className="card-icon"><Icon name="key" /></div>
        <h2 id="code-title">Portföy kodu</h2>
      </header>
      <div className="code-card-row">
        <span className="code-big" aria-label={`Kod ${current.code.split("").join(" ")}`}>{current.code}</span>
        <div className="btn-row">
          <button className="btn" type="button" onClick={() => copyCode(current.code, toast)}><Icon name="copy" size={15} /> Kopyala</button>
          {access === "code" ? (
            <button className="btn" type="button" onClick={onLeave}><Icon name="x" size={15} /> Bu cihazda kapat</button>
          ) : (
            <button className="btn" type="button" onClick={renew} disabled={busy}><Icon name="refresh" size={15} /> Yeni kod</button>
          )}
        </div>
      </div>
    </section>
  );
}

export default function Account({ dash, access, onLeave }) {
  const owner = access !== "code";
  return (
    <motion.div className="stack" variants={stagger(0.08)} initial="hidden" animate="show">
      <motion.div variants={fadeUp}><PortfolioCode dash={dash} access={access} onLeave={onLeave} /></motion.div>
      {owner && <motion.div variants={fadeUp}><Identity onCompleted={dash.refreshAfterIdentity} /></motion.div>}
      {owner && <motion.div variants={fadeUp}><Tax identityReady={dash.identityReady} /></motion.div>}
      {owner && <motion.div variants={fadeUp}><DataRights dash={dash} /></motion.div>}
      <motion.section variants={fadeUp} className="card">
        <header className="card-head">
          <div className="card-icon"><Icon name="swap" /></div>
          <h2>Arayüz</h2>
        </header>
        <div className="rights-row">
          <p className="muted">Önceki arayüze geçin; buradan geri dönebilirsiniz.</p>
          <button className="btn" type="button" onClick={() => switchUi("classic")}>Klasik arayüz</button>
        </div>
      </motion.section>
      <motion.footer variants={fadeUp} className="legal" aria-label="Bilgilendirmeler">
        <span>Gizlilik: Özel Portföy verileri Operator araçlarına veya normal loglara girmez.</span>
        <span>Koşullar: faðir beta kişisel kullanım içindir.</span>
        <span>Vergi: Turkey Tax Estimate vergi danışmanlığı değildir.</span>
        <span>Piyasa verisi: Beta mevcut Yahoo kaynağını kullanır.</span>
        <span>Guest saklama: Erişimsiz Guest verileri 90 gün sonra silinir.</span>
      </motion.footer>
    </motion.div>
  );
}
