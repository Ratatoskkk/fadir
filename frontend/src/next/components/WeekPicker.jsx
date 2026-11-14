// The Ticker view's "Weeks" range. The last four weeks are buttons: a click charts that
// week alone, Ctrl (Cmd on a Mac) + click adds or removes one. Any other stretch is typed
// as From and To week numbers and charts every week between them, both included.

import { useState } from "react";
import { motion } from "framer-motion";
import { dayMonth } from "../../format.js";
import { useT } from "../i18n/index.jsx";
import Icon from "../ui/Icons.jsx";
import Popover from "../ui/Popover.jsx";
import { spring } from "../ui/motion.js";

/** Matches the server's limit: a typed range may cover a whole year. */
export const MAX_WEEKS = 53;
const DAY = 86400000;
const RECENT = 4;

/** ISO [year, week] of a date, by its UTC calendar day. */
export function isoWeek(ms) {
  const d = new Date(ms);
  const t = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  const thursday = t + (4 - (new Date(t).getUTCDay() || 7)) * DAY;
  const year = new Date(thursday).getUTCFullYear();
  return [year, Math.floor((thursday - Date.UTC(year, 0, 1)) / DAY / 7) + 1];
}

/** UTC midnight of the Monday of ISO week `week` in `year`. */
export function mondayOf(year, week) {
  const jan4 = Date.UTC(year, 0, 4);
  return jan4 - ((new Date(jan4).getUTCDay() || 7) - 1) * DAY + (week - 1) * 7 * DAY;
}

export const weekKey = (year, week) => `${year}-W${String(week).padStart(2, "0")}`;
export const parseWeekKey = (key) => key.split("-W").map(Number);
const weeksIn = (year) => isoWeek(Date.UTC(year, 11, 28))[1];
const keyOf = (monday) => weekKey(...isoWeek(monday));

function todayUtc() {
  const now = new Date();
  return Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
}

/**
 * Every week from `from` to `to` in `year`, both included, or an error key. A From above
 * To runs over New Year: From in the year before, To in `year`.
 */
export function weekRange(year, from, to, today) {
  const startYear = from > to ? year - 1 : year;
  if (from < 1 || from > weeksIn(startYear)) return { error: "ticker.weekMissing", n: from, year: startYear };
  if (to < 1 || to > weeksIn(year)) return { error: "ticker.weekMissing", n: to, year };
  const first = mondayOf(startYear, from);
  if (first > today) return { error: "ticker.weekFuture", n: from };
  // A To week still to come stops at the current week.
  const last = Math.min(mondayOf(year, to), today - ((new Date(today).getUTCDay() || 7) - 1) * DAY);
  const weeks = [];
  for (let m = first; m <= last; m += 7 * DAY) weeks.push(keyOf(m));
  if (weeks.length > MAX_WEEKS) return { error: "ticker.weekTooMany", n: MAX_WEEKS };
  return { weeks };
}

function RangeForm({ onApply }) {
  const t = useT();
  const today = todayUtc();
  const [year, setYear] = useState(() => isoWeek(today)[0]);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [error, setError] = useState(null);

  const submit = (e) => {
    e.preventDefault();
    const f = Number(from), tw = Number(to || from);
    if (!Number.isInteger(f) || !Number.isInteger(tw) || !from) { setError({ error: "ticker.weekNumbers" }); return; }
    const result = weekRange(year, f, tw, today);
    if (result.error) { setError(result); return; }
    setError(null);
    onApply(result.weeks);
  };

  return (
    <form className="week-range" onSubmit={submit} noValidate>
      <div className="week-year">
        <button type="button" className="icon-btn" onClick={() => setYear((y) => y - 1)} aria-label={t("ticker.prevYear")}>
          <Icon name="left" size={16} />
        </button>
        <span className="num" aria-live="polite">{year}</span>
        <button type="button" className="icon-btn" onClick={() => setYear((y) => y + 1)} disabled={year >= isoWeek(today)[0]} aria-label={t("ticker.nextYear")}>
          <Icon name="right" size={16} />
        </button>
      </div>
      <div className="week-fields">
        <label className="field">
          <span>{t("ticker.fromWeek")}</span>
          <input className="num" inputMode="numeric" maxLength={2} value={from} onChange={(e) => setFrom(e.target.value.replace(/\D/g, ""))} />
        </label>
        <label className="field">
          <span>{t("ticker.toWeek")}</span>
          <input className="num" inputMode="numeric" maxLength={2} value={to} onChange={(e) => setTo(e.target.value.replace(/\D/g, ""))} />
        </label>
        <button type="submit" className="btn primary">{t("ticker.showWeeks")}</button>
      </div>
      {error && <p className="week-error" role="alert">{t(error.error, error)}</p>}
    </form>
  );
}

export function WeekPicker({ weeks, active, onChange }) {
  const t = useT();
  const today = todayUtc();
  // This week and the three before it, oldest first.
  const thisMonday = today - ((new Date(today).getUTCDay() || 7) - 1) * DAY;
  const recent = Array.from({ length: RECENT }, (_, k) => thisMonday - (RECENT - 1 - k) * 7 * DAY)
    .map((monday) => ({ monday, key: keyOf(monday), week: isoWeek(monday)[1] }));
  // Weeks picked earlier only count while the Weeks range is the one on screen.
  const current = active ? weeks : [];
  const chosen = new Set(current);

  const label = !active || !weeks.length
    ? t("ticker.range.W")
    : weeks.length === 1
      ? t("ticker.weekShort", { n: parseWeekKey(weeks[0])[1] })
      : t("ticker.weeksCount", { n: weeks.length });

  const pick = (key, add, close) => {
    if (!add) {
      onChange([key]);
      close();
      return;
    }
    const next = chosen.has(key) ? current.filter((k) => k !== key) : [...current, key];
    if (next.length && next.length <= MAX_WEEKS) onChange(next.sort());
  };

  return (
    <Popover
      label={t("ticker.chooseWeeks")}
      align="right"
      className="week-pop"
      trigger={({ open, toggle }) => (
        <button type="button" aria-pressed={active} aria-expanded={open} aria-haspopup="dialog" onClick={toggle}>
          {active && <motion.span layoutId="ticker-range-pill" className="segmented-pill" transition={spring} />}
          <span>{label}</span>
        </button>
      )}
    >
      {({ close }) => (
        <div className="week-picker">
          <div className="week-recent">
            {recent.map(({ monday, key, week }) => (
              <button
                key={key}
                type="button"
                className="week-cell"
                aria-pressed={chosen.has(key)}
                aria-label={t("ticker.weekLabel", { n: week, from: dayMonth(monday), to: dayMonth(monday + 6 * DAY) })}
                onClick={(e) => pick(key, e.ctrlKey || e.metaKey, close)}
              >
                <b className="num">{t("ticker.weekShort", { n: week })}</b>
                <span className="num">{dayMonth(monday)}</span>
              </button>
            ))}
          </div>
          <p className="week-hint"><kbd>Ctrl</kbd> + {t("ticker.weekAddHint")}</p>
          <RangeForm onApply={(next) => { onChange(next); close(); }} />
        </div>
      )}
    </Popover>
  );
}
