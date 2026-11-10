// First screen for a browser with no access yet: type a Portfolio Code to open it here.
// Signing in with Google or starting a new Portfolio sit quietly below.
//
// One real <input> lies over the digit slots, so the phone number pad, paste and
// one-time-code autofill all work; the slots only draw what it holds.

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useAnimationControls } from "framer-motion";
import { api } from "../../api.js";
import Icon from "../ui/Icons.jsx";
import { sound } from "../ui/sound.js";
import Brand from "./Brand.jsx";
import { useT } from "../i18n/index.jsx";

const shake = { x: [0, -14, 12, -9, 6, -3, 0], transition: { duration: 0.42 } };

export default function CodeGate({ codeLengths = [4], onOpened, onGoogle, onCreate }) {
  const t = useT();
  const lengths = codeLengths.length ? codeLengths : [4];
  const size = Math.max(...lengths);
  const [code, setCode] = useState("");
  const [state, setState] = useState("idle"); // idle | checking | wrong | open | busy
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  const row = useAnimationControls();

  useEffect(() => { inputRef.current?.focus(); }, []);

  async function submit(value) {
    if (!lengths.includes(value.length) || state === "checking" || state === "open") return;
    setState("checking");
    setError(null);
    try {
      await api.openCode(value);
      sound.open();
      setState("open");
      window.setTimeout(() => onOpened(), 650);
    } catch (err) {
      sound.wrong();
      setState("wrong");
      setError(err?.status === 429 ? t("code.throttled") : err?.status === 404 ? null : t("common.offline"));
      await row.start(shake);
      setCode("");
      setState("idle");
      inputRef.current?.focus();
    }
  }

  function onChange(event) {
    if (state === "checking" || state === "open") return;
    const next = event.target.value.replace(/\D/g, "").slice(0, size);
    if (next.length > code.length) sound.key();
    else if (next.length < code.length) sound.erase();
    setCode(next);
    if (error) setError(null);
    if (next.length === size) submit(next);
  }

  function onKeyDown(event) {
    if (event.key === "Enter") submit(code);
  }

  async function leave(action) {
    setState("busy");
    setError(null);
    try {
      await action();
    } catch {
      setError(t("common.offline"));
      setState("idle");
    }
  }

  const busy = state === "busy";
  return (
    <div className="gate">
      <motion.main
        className="gate-panel"
        initial={{ opacity: 0, y: 16 }}
        animate={state === "open" ? { opacity: 0, y: -12, scale: 0.98, transition: { delay: 0.35, duration: 0.3 } } : { opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="gate-brand">
          <Brand size={34} />
          <span className="wordmark">faðir</span>
        </div>
        <h1 id="gate-title" className="gate-title">{t("code.title")}</h1>

        <motion.label className={`code-row ${state}`} animate={row} htmlFor="gate-code">
          <input
            id="gate-code"
            ref={inputRef}
            className="code-input"
            value={code}
            onChange={onChange}
            onKeyDown={onKeyDown}
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]*"
            maxLength={size}
            aria-labelledby="gate-title"
            aria-invalid={state === "wrong"}
            disabled={busy}
          />
          {Array.from({ length: size }, (_, i) => {
            const digit = code[i];
            const active = i === code.length && state === "idle";
            return (
              <span key={i} className={`code-slot ${digit ? "filled" : ""} ${active ? "active" : ""}`} aria-hidden="true">
                <AnimatePresence initial={false}>
                  {digit && (
                    <motion.span
                      key={`${i}-${digit}`}
                      className="code-digit num"
                      initial={{ y: 10, scale: 0.6, opacity: 0 }}
                      animate={{ y: 0, scale: 1, opacity: 1 }}
                      exit={{ scale: 0.6, opacity: 0, transition: { duration: 0.1 } }}
                      transition={{ type: "spring", stiffness: 700, damping: 26 }}
                    >
                      {digit}
                    </motion.span>
                  )}
                </AnimatePresence>
                {state === "open" && (
                  <motion.i
                    className="code-glow"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.05 }}
                  />
                )}
              </span>
            );
          })}
        </motion.label>

        <div className="gate-status" role="status" aria-live="polite">
          {state === "checking" && <span className="spinner" />}
          {error && <span className="down">{error}</span>}
        </div>

        <div className="gate-alt">
          <button type="button" className="btn ghost small" onClick={() => leave(onGoogle)} disabled={busy}>
            <Icon name="user" size={14} /> {t("code.google")}
          </button>
          <span className="gate-dot" aria-hidden="true" />
          <button type="button" className="btn ghost small" onClick={() => leave(onCreate)} disabled={busy}>
            <Icon name="plus" size={14} /> {t("code.create")}
          </button>
        </div>
      </motion.main>
    </div>
  );
}
