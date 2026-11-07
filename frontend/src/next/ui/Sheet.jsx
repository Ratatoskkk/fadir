// Slide-over panel from the right (bottom on phones).

import { useEffect } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import Icon from "./Icons.jsx";
import { spring } from "./motion.js";

export default function Sheet({ open, onClose, title, children }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const narrow = window.matchMedia("(max-width: 860px)").matches;
  const off = narrow ? { y: "100%" } : { x: "104%" };
  const on = narrow ? { y: 0 } : { x: 0 };

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="sheet"
          className="scrim sheet-scrim"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.2 } }}
          onMouseDown={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.aside
            className="sheet"
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={off}
            animate={{ ...on, transition: spring }}
            exit={{ ...off, transition: { duration: 0.22, ease: [0.4, 0, 1, 1] } }}
          >
            <header className="sheet-head">
              <h2>{title}</h2>
              <button type="button" className="icon-btn" onClick={onClose} aria-label="Kapat">
                <Icon name="x" />
              </button>
            </header>
            <div className="sheet-body">{children}</div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
