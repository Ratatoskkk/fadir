import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Icon from "../ui/Icons.jsx";
import { collapse } from "../ui/motion.js";
import { dateTimeStamp } from "../../format.js";
import { useT } from "../i18n/index.jsx";

function Notice({ tone, icon, children, onClose }) {
  const t = useT();
  return (
    <motion.div className="notice-wrap" layout {...collapse}>
      <div className={`notice notice-${tone}`} role={tone === "err" ? "alert" : "status"}>
        <Icon name={icon} size={16} />
        <div className="notice-body">{children}</div>
        {onClose && (
          <button type="button" className="icon-btn" aria-label={t("common.dismiss")} onClick={onClose}>
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
  const t = useT();

  return (
    <div className="notices">
      <AnimatePresence initial={false}>
        {error && (
          <Notice key="err" tone="err" icon="alert">
            <strong>{t("notice.connection")}</strong> {error}
          </Notice>
        )}
        {guestAccess?.noticeDue && !guestDismissed && (
          <Notice key="guest" tone="warn" icon="clock" onClose={() => setGuestDismissed(true)}>
            <strong>{t("notice.guestTitle")}</strong> {t("notice.guestExpires", { date: dateTimeStamp(guestAccess.expiresAt) })}
          </Notice>
        )}
        {failed.length > 0 && (
          <Notice key="failed" tone="warn" icon="alert">
            <strong>{t("notice.unpriced", { n: failed.length })}</strong> {t("notice.unpricedNote")}{" "}
            <span className="muted">{failed.map((p) => `${p.ticker}: ${p.error ?? t("common.noData")}`).join(", ")}</span>
          </Notice>
        )}
        {carried.length > 0 && (
          <Notice key="carried" tone="info" icon="info">
            {t("notice.carried", { n: carried.length, tickers: carried.map((p) => p.ticker).join(", ") })}
          </Notice>
        )}
      </AnimatePresence>
    </div>
  );
}
