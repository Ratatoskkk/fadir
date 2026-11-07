// Google identity: sign in, then an explicit choice for the Guest data (claim, transfer,
// merge). Same state machine as the classic panel, drawn as a stepper.

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../../api.js";
import { loadGoogleIdentityServices } from "../../google.js";
import Icon from "../ui/Icons.jsx";
import { collapse, spring } from "../ui/motion.js";
import Merge from "./Merge.jsx";

const CHOICES = [
  { key: "claim", title: "Claim", text: "Guest Workspace bu User'a bağlanır; Portföyler ve işlemler aynı yerde kalır." },
  { key: "transfer", title: "Portfolio Transfer", text: "Guest Portföyleri User Workspace içine ayrı Portföyler olarak taşınır." },
  { key: "merge", title: "Portfolio Merge", text: "Guest işlemleri seçtiğiniz User Portföyüne birleştirilir." },
];

export default function Identity({ onCompleted }) {
  const [phase, setPhase] = useState("checking");
  const [choice, setChoice] = useState(null);
  const [rename, setRename] = useState("");
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [mergeReady, setMergeReady] = useState(false);
  const nonceRef = useRef(null);
  const googleButtonRef = useRef(null);
  const googleIdentityRef = useRef(null);
  const hydrationRequestRef = useRef(0);

  const hydrateUserSession = useCallback(async () => {
    const requestId = hydrationRequestRef.current + 1;
    hydrationRequestRef.current = requestId;
    setPhase("checking");
    setError(null);
    try {
      await api.userSessions();
      if (hydrationRequestRef.current !== requestId) return;
      setPhase("signed-in");
    } catch (err) {
      if (hydrationRequestRef.current !== requestId) return;
      if (err?.status === 401) {
        setPhase("idle");
        return;
      }
      setError("User oturumu doğrulanamadı. Tekrar deneyin.");
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    hydrateUserSession();
    return () => {
      hydrationRequestRef.current += 1;
    };
  }, [hydrateUserSession]);

  useEffect(() => {
    if (phase !== "awaiting" || !googleIdentityRef.current || !googleButtonRef.current) return;
    const identity = googleIdentityRef.current;
    if (identity.renderButton) {
      identity.renderButton(googleButtonRef.current, {
        theme: document.documentElement.dataset.theme === "light" ? "outline" : "filled_black",
        size: "large",
        shape: "pill",
      });
    }
  }, [phase]);

  const verifyCredential = useCallback(async (credential) => {
    const nonce = nonceRef.current;
    nonceRef.current = null;
    if (typeof credential !== "string" || !nonce) {
      setError("Google doğrulaması geçerli bir kimlik bilgisi döndürmedi.");
      setPhase("idle");
      return;
    }
    setPhase("verifying");
    setError(null);
    try {
      await api.googleVerify({ credential, nonce });
      setPhase("choice");
    } catch (err) {
      setError(`Google kimliği doğrulanamadı: ${err.message}`);
      setPhase("idle");
    }
  }, []);

  async function startSignIn() {
    hydrationRequestRef.current += 1;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const start = await api.googleStart();
      nonceRef.current = start.nonce;
      const google = await loadGoogleIdentityServices();
      const identity = google?.accounts?.id;
      if (!identity?.initialize) throw new Error("Google doğrulaması hazır değil.");
      identity.initialize({
        client_id: start.client_id,
        nonce: start.nonce,
        callback: ({ credential }) => verifyCredential(credential),
      });
      googleIdentityRef.current = identity;
      setPhase("awaiting");
      if (!identity.renderButton && identity.prompt) identity.prompt();
      else if (!identity.renderButton) throw new Error("Google doğrulama düğmesi hazır değil.");
    } catch (err) {
      nonceRef.current = null;
      setError(`Google girişi başlatılamadı: ${err.message}`);
      setPhase("idle");
    } finally {
      setBusy(false);
    }
  }

  async function applyChoice(action) {
    setBusy(true);
    setError(null);
    try {
      const payload = { action };
      if (action === "transfer") payload.rename = rename.trim() || null;
      const value = await api.googleTransition(payload);
      setResult(value);
      setPhase("complete");
      await onCompleted?.();
    } catch (err) {
      setError(`Seçim uygulanamadı: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function chooseMerge() {
    if (mergeReady) return;
    setChoice("merge");
    setMergeReady(false);
    setBusy(true);
    setError(null);
    try {
      await api.googleTransition({ action: "merge" });
      setMergeReady(true);
    } catch (err) {
      setError(`Merge seçimi uygulanamadı: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function completeMerge() {
    setResult({ action: "merge" });
    setPhase("complete");
    await onCompleted?.();
  }

  const pick = (key) => (key === "merge" ? chooseMerge() : setChoice(key));

  return (
    <section className="card identity" aria-labelledby="identity-title">
      <header className="card-head">
        <div className="card-icon"><Icon name="user" /></div>
        <h2 id="identity-title">Google ile kimlik</h2>
        <AnimatePresence mode="popLayout">
          <motion.span key={phase} className={`status-chip ${phase === "signed-in" || phase === "complete" ? "ok" : ""}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            {phase === "signed-in" || phase === "complete" ? "etkin" : phase === "checking" ? "kontrol" : "misafir"}
          </motion.span>
        </AnimatePresence>
      </header>

      <AnimatePresence>{error && <motion.div className="form-error" role="alert" {...collapse}><div>{error}</div></motion.div>}</AnimatePresence>

      {/* Keyed remount, not AnimatePresence "wait": the Google button node must exist the
          moment the phase flips to "awaiting", or renderButton finds nothing to draw into. */}
      <motion.div key={phase} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.26 }}>
          {phase === "idle" && (
            <div className="identity-start">
              <p className="muted">Kurtarma ve uzun süreli saklama için User Workspace'e geçin. Guest veriniz için açık bir seçim yaparsınız.</p>
              <button className="btn primary" type="button" onClick={startSignIn} disabled={busy}>
                {busy ? <span className="spinner" /> : "Google ile devam et"}
              </button>
            </div>
          )}
          {phase === "checking" && <p className="muted" role="status" aria-busy="true"><span className="spinner" /> User oturumu kontrol ediliyor…</p>}
          {phase === "error" && (
            <div className="identity-start">
              <p className="muted">User oturumu kontrol edilemedi.</p>
              <button className="btn ghost" type="button" onClick={hydrateUserSession}>Tekrar dene</button>
            </div>
          )}
          {phase === "signed-in" && <p className="muted" role="status">Google User oturumu etkin. Bu tarayıcı User Workspace erişimine sahip.</p>}
          {(phase === "awaiting" || phase === "verifying") && (
            <div role="status" aria-live="polite" className="identity-wait">
              <p className="muted">{phase === "verifying" ? "Google kimliği doğrulanıyor…" : "Google kimlik doğrulaması bekleniyor…"}</p>
              <div ref={googleButtonRef} className="google-button" />
            </div>
          )}
          {phase === "choice" && (
            <div className="identity-choice">
              <p role="status">Google kimliği doğrulandı. Guest veriniz için bir işlem seçin.</p>
              <div className="choice-grid" role="group" aria-label="Guest verisi işlemi">
                {CHOICES.map((c) => (
                  <motion.button
                    key={c.key}
                    type="button"
                    className={`choice ${choice === c.key ? "on" : ""}`}
                    aria-pressed={choice === c.key}
                    onClick={() => pick(c.key)}
                    disabled={busy}
                    whileHover={{ y: -3 }}
                    whileTap={{ scale: 0.98 }}
                    transition={spring}
                  >
                    <strong>{c.title}</strong>
                    <span>{c.text}</span>
                  </motion.button>
                ))}
              </div>
              <AnimatePresence mode="wait">
                {choice === "claim" && (
                  <motion.div key="claim" {...collapse} className="choice-detail">
                    <div><button className="btn primary" type="button" onClick={() => applyChoice("claim")} disabled={busy}>Claim'i onayla</button></div>
                  </motion.div>
                )}
                {choice === "transfer" && (
                  <motion.div key="transfer" {...collapse} className="choice-detail">
                    <div>
                      <div className="field">
                        <label htmlFor="transfer-rename">Yeni ad (isteğe bağlı)</label>
                        <input id="transfer-rename" value={rename} onChange={(e) => setRename(e.target.value)} maxLength={128} />
                      </div>
                      <button className="btn primary" type="button" onClick={() => applyChoice("transfer")} disabled={busy}>Transfer'i onayla</button>
                    </div>
                  </motion.div>
                )}
                {choice === "merge" && !mergeReady && (
                  <motion.p key="merge-wait" className="muted" role="status" aria-busy={busy} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    {busy ? "Portfolio Merge hazırlanıyor…" : "Portfolio Merge geçişi tamamlanamadı; tekrar deneyin."}
                  </motion.p>
                )}
                {choice === "merge" && mergeReady && (
                  <motion.div key="merge" {...collapse}><Merge onCompleted={completeMerge} /></motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
          {phase === "complete" && (
            <div className="success" role="status">
              <motion.span className="success-check" initial={{ scale: 0, rotate: -40 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 400, damping: 14 }}>
                <Icon name="check" size={20} />
              </motion.span>
              {result?.action === "merge" ? "Portfolio Merge tamamlandı." : `${result?.action ?? "Seçim"} tamamlandı.`}
            </div>
          )}
      </motion.div>
    </section>
  );
}
