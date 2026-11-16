// Modal pop-ups on the native <dialog>. showModal() makes the page inert, keeps focus
// inside, puts the pop-up in the top layer and turns Esc into a `cancel` event; closing
// returns focus to whatever opened it. React still owns open and closed, so the browser
// is asked to close only after the exit animation has played.

import { useId, useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useIsPresent } from "framer-motion";
import { useT } from "../i18n/index.jsx";
import Icon from "./Icons.jsx";

const FIRST_FIELD = "input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea:not([disabled])";
/** Longer than any exit animation here (0.12–0.16s). */
const EXIT_MS = 250;

const outside = (e, el) => {
  const r = el.getBoundingClientRect();
  return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
};

/**
 * The <dialog> itself. Esc, the back gesture and a press-and-release on the backdrop call
 * onClose; `initialFocus` (a ref) wins over the first form field, which wins over the
 * browser's default of the first focusable element.
 */
export function Modal({ onClose, initialFocus, className = "", children, ...props }) {
  const ref = useRef(null);
  const present = useIsPresent();
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Layout effect: open before first paint, and close before React detaches the node so
  // the browser still returns focus to the opener.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el.open) el.showModal();
    (initialFocus?.current ?? el.querySelector(FIRST_FIELD))?.focus();

    const onCancel = (e) => { e.preventDefault(); onCloseRef.current(); };
    let pressedOutside = false;
    const onDown = (e) => { pressedOutside = e.target === el && outside(e, el); };
    const onUp = (e) => {
      if (pressedOutside && e.target === el && outside(e, el)) onCloseRef.current();
      pressedOutside = false;
    };
    el.addEventListener("cancel", onCancel);
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointerup", onUp);
    return () => {
      el.removeEventListener("cancel", onCancel);
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointerup", onUp);
      if (el.open) el.close();
    };
    // initialFocus is read once on open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The exit animation runs on animation frames, and a background tab or a covered or
  // minimised window gets none (Firefox stops them outright), so it can stall with the
  // dialog transparent but still modal: the whole page stays inert. The browser is told
  // to close once the exit's time is up, frames or not; reopened mid-exit, it shows again.
  useLayoutEffect(() => {
    const el = ref.current;
    if (present) {
      if (!el.open) el.showModal();
      return undefined;
    }
    const id = window.setTimeout(() => { if (el.open) el.close(); }, EXIT_MS);
    return () => window.clearTimeout(id);
  }, [present]);

  return (
    <motion.dialog ref={ref} className={className} data-closing={present ? undefined : ""} {...props}>
      {children}
    </motion.dialog>
  );
}

export default function Dialog({ open, onClose, title, children, className = "" }) {
  const t = useT();
  const titleId = useId();
  return createPortal(
    <AnimatePresence>
      {open && (
        <Modal
          key="dialog"
          onClose={onClose}
          className={`modal ${className}`}
          aria-labelledby={titleId}
          initial={{ opacity: 0, y: 24, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 420, damping: 32 } }}
          exit={{ opacity: 0, y: 12, scale: 0.97, transition: { duration: 0.16 } }}
        >
          <header className="modal-head">
            <h2 id={titleId}>{title}</h2>
            <button type="button" className="icon-btn" onClick={onClose} aria-label={t("common.close")}>
              <Icon name="x" />
            </button>
          </header>
          <div className="modal-body">{children}</div>
        </Modal>
      )}
    </AnimatePresence>,
    document.body,
  );
}
