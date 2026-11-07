// Ctrl/⌘ K: every navigation and action in one searchable list.

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import Icon from "../ui/Icons.jsx";
import { spring } from "../ui/motion.js";
import { useT } from "../i18n/index.jsx";

const fold = (s) => s.toLocaleLowerCase("tr").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i");

function Palette({ commands, onClose }) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  const results = useMemo(() => {
    const q = fold(query.trim());
    if (!q) return commands;
    const words = q.split(/\s+/);
    return commands.filter((c) => {
      const hay = fold(`${c.group} ${c.label} ${c.keywords ?? ""}`);
      return words.every((w) => hay.includes(w));
    });
  }, [commands, query]);

  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => { setActive(0); }, [query]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const run = (cmd) => {
    onClose();
    window.setTimeout(() => cmd.run(), 0);
  };

  const onKey = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(results.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(0, i - 1)); }
    else if (e.key === "Enter" && results[active]) { e.preventDefault(); run(results[active]); }
    else if (e.key === "Escape") { e.preventDefault(); onClose(); }
  };

  let lastGroup = null;
  return (
    <motion.div className="scrim palette-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.15 } }} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <motion.div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label={t("palette.title")}
        initial={{ opacity: 0, y: -20, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1, transition: spring }}
        exit={{ opacity: 0, y: -10, scale: 0.98, transition: { duration: 0.12 } }}
      >
        <div className="palette-input">
          <Icon name="search" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder={t("palette.placeholder")}
            aria-label={t("palette.search")}
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-list"
            aria-activedescendant={results[active] ? `cmd-${active}` : undefined}
          />
          <kbd>Esc</kbd>
        </div>
        <div className="palette-list" id="palette-list" role="listbox" ref={listRef}>
          {results.length === 0 && <div className="palette-empty">{t("common.noResults")}</div>}
          {results.map((c, i) => {
            const header = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <div key={c.id}>
                {header && <div className="menu-label">{header}</div>}
                <button
                  type="button"
                  id={`cmd-${i}`}
                  data-index={i}
                  role="option"
                  aria-selected={i === active}
                  className={`palette-item ${i === active ? "on" : ""}`}
                  onMouseMove={() => i !== active && setActive(i)}
                  onClick={() => run(c)}
                >
                  {i === active && <motion.span layoutId="palette-hl" className="palette-hl" transition={{ ...spring, stiffness: 700 }} />}
                  <Icon name={c.icon ?? "sparkle"} size={16} />
                  <span>{c.label}</span>
                  {c.hint && <span className="muted palette-hint">{c.hint}</span>}
                </button>
              </div>
            );
          })}
        </div>
      </motion.div>
    </motion.div>
  );
}

export default function CommandPalette({ open, onClose, commands }) {
  return createPortal(
    <AnimatePresence>{open && <Palette key="palette" commands={commands} onClose={onClose} />}</AnimatePresence>,
    document.body,
  );
}
