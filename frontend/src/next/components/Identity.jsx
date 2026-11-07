// Google identity: sign in, then an explicit choice for the Guest data (claim, transfer,
// merge). Same state machine as the classic panel, drawn as a stepper.

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../../api.js";
import { loadGoogleIdentityServices } from "../../google.js";
import Icon from "../ui/Icons.jsx";
import { collapse, spring } from "../ui/motion.js";
import Merge from "./Merge.jsx";
import { useT } from "../i18n/index.jsx";

const CHOICES = [
  { key: "claim", title: "identity.claim", text: "identity.claimText" },
  { key: "transfer", title: "identity.transfer", text: "identity.transferText" },
  { key: "merge", title: "identity.merge", text: "identity.mergeText" },
];

export default function Identity({ onCompleted }) {
  const t = useT();
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
  const startRef = useRef(null);

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
        // Chosen on the code screen: go straight to the Google step.
        let intent = false;
        try {
          intent = sessionStorage.getItem("fadir.google-intent") === "1";
          sessionStorage.removeItem("fadir.google-intent");
        } catch { /* private mode */ }
        if (intent) startRef.current?.();
        return;
      }
      setError(t("identity.checkFailed"));
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
      setError(t("identity.noCredential"));
      setPhase("idle");
      return;
    }
    setPhase("verifying");
    setError(null);
    try {
      await api.googleVerify({ credential, nonce });
      setPhase("choice");
    } catch (err) {
      setError(t("identity.verifyFailed", { error: err.message }));
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
      if (!identity?.initialize) throw new Error(t("identity.notReady"));
      identity.initialize({
        client_id: start.client_id,
        nonce: start.nonce,
        callback: ({ credential }) => verifyCredential(credential),
      });
      googleIdentityRef.current = identity;
      setPhase("awaiting");
      if (!identity.renderButton && identity.prompt) identity.prompt();
      else if (!identity.renderButton) throw new Error(t("identity.buttonNotReady"));
    } catch (err) {
      nonceRef.current = null;
      setError(t("identity.startFailed", { error: err.message }));
      setPhase("idle");
    } finally {
      setBusy(false);
    }
  }

  startRef.current = startSignIn;

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
      setError(t("identity.choiceFailed", { error: err.message }));
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
      setError(t("identity.mergeFailed", { error: err.message }));
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
        <h2 id="identity-title">{t("identity.title")}</h2>
        <AnimatePresence mode="popLayout">
          <motion.span key={phase} className={`status-chip ${phase === "signed-in" || phase === "complete" ? "ok" : ""}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            {t(phase === "signed-in" || phase === "complete" ? "identity.active" : phase === "checking" ? "identity.checking" : "identity.guest")}
          </motion.span>
        </AnimatePresence>
      </header>

      <AnimatePresence>{error && <motion.div className="form-error" role="alert" {...collapse}><div>{error}</div></motion.div>}</AnimatePresence>

      {/* Keyed remount, not AnimatePresence "wait": the Google button node must exist the
          moment the phase flips to "awaiting", or renderButton finds nothing to draw into. */}
      <motion.div key={phase} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.26 }}>
          {phase === "idle" && (
            <div className="identity-start">
              <p className="muted">{t("identity.intro")}</p>
              <button className="btn primary" type="button" onClick={startSignIn} disabled={busy}>
                {busy ? <span className="spinner" /> : t("identity.continue")}
              </button>
            </div>
          )}
          {phase === "checking" && <p className="muted" role="status" aria-busy="true"><span className="spinner" /> {t("identity.checkingLong")}</p>}
          {phase === "error" && (
            <div className="identity-start">
              <p className="muted">{t("identity.checkError")}</p>
              <button className="btn ghost" type="button" onClick={hydrateUserSession}>{t("common.retry")}</button>
            </div>
          )}
          {phase === "signed-in" && <p className="muted" role="status">{t("identity.signedIn")}</p>}
          {(phase === "awaiting" || phase === "verifying") && (
            <div role="status" aria-live="polite" className="identity-wait">
              <p className="muted">{t(phase === "verifying" ? "identity.verifying" : "identity.waiting")}</p>
              <div ref={googleButtonRef} className="google-button" />
            </div>
          )}
          {phase === "choice" && (
            <div className="identity-choice">
              <p role="status">{t("identity.verified")}</p>
              <div className="choice-grid" role="group" aria-label={t("identity.choiceGroup")}>
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
                    <strong>{t(c.title)}</strong>
                    <span>{t(c.text)}</span>
                  </motion.button>
                ))}
              </div>
              <AnimatePresence mode="wait">
                {choice === "claim" && (
                  <motion.div key="claim" {...collapse} className="choice-detail">
                    <div><button className="btn primary" type="button" onClick={() => applyChoice("claim")} disabled={busy}>{t("identity.confirmClaim")}</button></div>
                  </motion.div>
                )}
                {choice === "transfer" && (
                  <motion.div key="transfer" {...collapse} className="choice-detail">
                    <div>
                      <div className="field">
                        <label htmlFor="transfer-rename">{t("identity.newName")}</label>
                        <input id="transfer-rename" value={rename} onChange={(e) => setRename(e.target.value)} maxLength={128} />
                      </div>
                      <button className="btn primary" type="button" onClick={() => applyChoice("transfer")} disabled={busy}>{t("identity.confirmTransfer")}</button>
                    </div>
                  </motion.div>
                )}
                {choice === "merge" && !mergeReady && (
                  <motion.p key="merge-wait" className="muted" role="status" aria-busy={busy} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    {t(busy ? "identity.mergePreparing" : "identity.mergeIncomplete")}
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
              {t(result?.action === "merge" ? "identity.mergeDone" : result?.action === "transfer" ? "identity.transferDone" : "identity.claimDone")}
            </div>
          )}
      </motion.div>
    </section>
  );
}
