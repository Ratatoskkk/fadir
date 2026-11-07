// Toasts and confirmation dialogs, both promise/imperative so call sites stay linear:
//   const confirm = useConfirm(); if (!(await confirm({...}))) return;
//   const toast = useToast(); toast({ tone: "up", text: "Kaydedildi" });

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Icon from "./Icons.jsx";
import { bouncy, ease, spring } from "./motion.js";
import { useT } from "../i18n/index.jsx";

const ToastContext = createContext(() => {});
const ConfirmContext = createContext(async () => false);

export const useToast = () => useContext(ToastContext);
export const useConfirm = () => useContext(ConfirmContext);

let nextId = 1;

export function OverlayProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const [dialog, setDialog] = useState(null);

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), []);

  const toast = useCallback((input) => {
    const item = { id: nextId++, tone: "info", ...(typeof input === "string" ? { text: input } : input) };
    setToasts((list) => [...list.slice(-3), item]);
    window.setTimeout(() => dismiss(item.id), item.duration ?? 4200);
  }, [dismiss]);

  const confirm = useCallback(
    (options) => new Promise((resolve) => setDialog({ ...options, resolve })),
    [],
  );

  const close = (answer) => {
    dialog?.resolve(answer);
    setDialog(null);
  };

  return (
    <ToastContext.Provider value={toast}>
      <ConfirmContext.Provider value={confirm}>
        {children}

        <div className="toasts" role="status" aria-live="polite">
          <AnimatePresence initial={false}>
            {toasts.map((t) => (
              <motion.div
                key={t.id}
                layout
                className={`toast toast-${t.tone}`}
                initial={{ opacity: 0, y: 24, scale: 0.92 }}
                animate={{ opacity: 1, y: 0, scale: 1, transition: bouncy }}
                exit={{ opacity: 0, x: 60, transition: { duration: 0.2, ease } }}
                onClick={() => dismiss(t.id)}
              >
                <Icon name={t.tone === "down" ? "alert" : t.tone === "up" ? "check" : "info"} size={16} />
                <span>{t.text}</span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        <AnimatePresence>
          {dialog && <ConfirmDialog key="confirm" dialog={dialog} onClose={close} />}
        </AnimatePresence>
      </ConfirmContext.Provider>
    </ToastContext.Provider>
  );
}

function ConfirmDialog({ dialog, onClose }) {
  const t = useT();
  const confirmRef = useRef(null);
  useEffect(() => {
    confirmRef.current?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") onClose(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <motion.div
      className="scrim"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.15 } }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose(false)}
    >
      <motion.div
        className="dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0, transition: spring }}
        exit={{ opacity: 0, scale: 0.95, y: 10, transition: { duration: 0.15 } }}
      >
        <div className={`dialog-icon ${dialog.danger ? "danger" : ""}`}>
          <Icon name={dialog.danger ? "trash" : "info"} size={20} />
        </div>
        <h3 id="confirm-title">{dialog.title}</h3>
        {dialog.body && <div className="dialog-body">{dialog.body}</div>}
        <div className="dialog-actions">
          <button type="button" className="btn ghost" onClick={() => onClose(false)}>
            {t("common.cancel")}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`btn ${dialog.danger ? "danger solid" : "primary"}`}
            onClick={() => onClose(true)}
          >
            {dialog.confirmLabel ?? "Onayla"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
