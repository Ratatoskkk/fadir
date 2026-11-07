import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Icon from "../ui/Icons.jsx";
import { collapse } from "../ui/motion.js";

const dfGuestExpiry = new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium", timeStyle: "short" });
function guestExpiryLabel(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? String(iso) : dfGuestExpiry.format(date);
}

function Notice({ tone, icon, children, onClose }) {
  return (
    <motion.div className="notice-wrap" layout {...collapse}>
      <div className={`notice notice-${tone}`} role={tone === "err" ? "alert" : "status"}>
        <Icon name={icon} size={16} />
        <div className="notice-body">{children}</div>
        {onClose && (
          <button type="button" className="icon-btn" aria-label="Bildirimi kapat" onClick={onClose}>
            <Icon name="x" size={14} />
          </button>
        )}
      </div>
    </motion.div>
  );
}

export default function Notices({ dash }) {
  const { error, guestAccess, portfolio } = dash;
  const [guestDismissed, setGuestDismissed] = useState(false);
  const positions = portfolio?.positions ?? [];
  const failed = positions.filter((p) => !p.ok);
  const carried = positions.filter((p) => p.fx_carried_forward);

  return (
    <div className="notices">
      <AnimatePresence initial={false}>
        {error && (
          <Notice key="err" tone="err" icon="alert">
            <strong>Bağlantı hatası:</strong> {error}
          </Notice>
        )}
        {guestAccess?.noticeDue && !guestDismissed && (
          <Notice key="guest" tone="warn" icon="clock" onClose={() => setGuestDismissed(true)}>
            <strong>Misafir çalışma alanı geçicidir.</strong> {guestExpiryLabel(guestAccess.expiresAt)} tarihinde sona erer.
          </Notice>
        )}
        {failed.length > 0 && (
          <Notice key="failed" tone="warn" icon="alert">
            <strong>{failed.length} pozisyon fiyatlanamadı</strong> — toplamlara dahil edilmedi.{" "}
            <span className="muted">{failed.map((p) => `${p.ticker}: ${p.error ?? "veri yok"}`).join(" · ")}</span>
          </Notice>
        )}
        {carried.length > 0 && (
          <Notice key="carried" tone="info" icon="info">
            {carried.length} pozisyonda kur önceki yayından taşındı ({carried.map((p) => p.ticker).join(", ")}).
          </Notice>
        )}
      </AnimatePresence>
    </div>
  );
}
