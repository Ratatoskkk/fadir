import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api.js";
import PortfolioMergePanel from "./PortfolioMergePanel.jsx";
import { loadGoogleIdentityServices } from "../../google.js";

export default function GoogleIdentityPanel({ onCompleted }) {
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
      identity.renderButton(googleButtonRef.current, { theme: "outline", size: "large" });
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
      if (!identity.renderButton && identity.prompt) {
        identity.prompt();
      } else if (!identity.renderButton) {
        throw new Error("Google doğrulama düğmesi hazır değil.");
      }
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

  return (
    <section className="panel identity-panel" aria-labelledby="identity-title">
      <div className="panel-head">
        <h2 id="identity-title">Google ile kimlik</h2>
        <span className="panel-sub">Kurtarma ve uzun süreli saklama için User Workspace seçin</span>
      </div>
      <div className="panel-body">
        {error && <div className="form-error" role="alert">{error}</div>}

        {phase === "idle" && (
          <div className="identity-start">
            <p className="hint">Google kimliği doğrulandıktan sonra Guest veriniz için açık bir seçim yaparsınız.</p>
            <button className="btn primary" type="button" onClick={startSignIn} disabled={busy}>
              {busy ? "başlatılıyor…" : "Google ile devam et"}
            </button>
          </div>
        )}

        {phase === "checking" && (
          <div className="identity-status" role="status" aria-live="polite" aria-busy="true">
            User oturumu kontrol ediliyor…
          </div>
        )}

        {phase === "error" && (
          <div className="identity-start">
            <p className="hint">User oturumu şu anda kontrol edilemedi. Google girişi başlatılmadı.</p>
            <button className="btn ghost" type="button" onClick={hydrateUserSession}>
              Tekrar dene
            </button>
          </div>
        )}

        {phase === "signed-in" && (
          <div className="identity-status" role="status" aria-live="polite">
            Google User oturumu etkin. Bu tarayıcı User Workspace erişimine sahip.
          </div>
        )}

        {(phase === "starting" || phase === "awaiting" || phase === "verifying") && (
          <div className="identity-status" role="status" aria-live="polite">
            {phase === "verifying" ? "Google kimliği doğrulanıyor…" : "Google kimlik doğrulaması bekleniyor…"}
            <div ref={googleButtonRef} className="google-button" />
          </div>
        )}

        {phase === "choice" && (
          <div className="identity-choice">
            <p role="status" aria-live="polite">Google kimliği doğrulandı. Guest veriniz için bir işlem seçin.</p>
            <div className="identity-actions" role="group" aria-label="Guest verisi işlemi">
              <button className={`btn ${choice === "claim" ? "primary" : "ghost"}`} type="button" aria-pressed={choice === "claim"} onClick={() => setChoice("claim")} disabled={busy}>
                Claim
              </button>
              <button className={`btn ${choice === "transfer" ? "primary" : "ghost"}`} type="button" aria-pressed={choice === "transfer"} onClick={() => setChoice("transfer")} disabled={busy}>
                Portfolio Transfer
              </button>
              <button className={`btn ${choice === "merge" ? "primary" : "ghost"}`} type="button" aria-pressed={choice === "merge"} onClick={chooseMerge} disabled={busy}>
                Portfolio Merge
              </button>
            </div>

            {choice === "claim" && (
              <div className="choice-detail">
                <p>Guest Workspace bu User'a bağlanır; Portföyler ve işlemler aynı yerde kalır.</p>
                <button className="btn primary" type="button" onClick={() => applyChoice("claim")} disabled={busy}>
                  Claim'i onayla
                </button>
              </div>
            )}
            {choice === "transfer" && (
              <div className="choice-detail">
                <p>Guest Portföyleri User Workspace içine ayrı Portföyler olarak taşınır.</p>
                <div className="field">
                  <label htmlFor="transfer-rename">Yeni ad (isteğe bağlı)</label>
                  <input id="transfer-rename" value={rename} onChange={(event) => setRename(event.target.value)} maxLength={128} />
                </div>
                <button className="btn primary" type="button" onClick={() => applyChoice("transfer")} disabled={busy}>
                  Transfer'i onayla
                </button>
              </div>
            )}
            {choice === "merge" && !mergeReady && (
              <div className="identity-status" role="status" aria-live="polite" aria-busy={busy}>
                {busy ? "Portfolio Merge hazırlanıyor…" : "Portfolio Merge geçişi tamamlanamadı; tekrar deneyin."}
              </div>
            )}
            {choice === "merge" && mergeReady && <PortfolioMergePanel onCompleted={completeMerge} />}
          </div>
        )}

        {phase === "complete" && (
          <div className="banner warn" role="status">
            {result?.action === "merge" ? "Portfolio Merge tamamlandı." : `${result?.action ?? "Seçim"} tamamlandı.`}
          </div>
        )}
      </div>
    </section>
  );
}
