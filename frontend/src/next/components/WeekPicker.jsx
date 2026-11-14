// The Ticker view's "Weeks" range: ISO weeks of one year, laid out by month. A click
// charts that week alone; Ctrl (Cmd on a Mac) + click adds or removes a week, so any
// set of weeks, adjacent or not, can be charted together.

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { dayMonth, monthName } from "../../format.js";
import { useT } from "../i18n/index.jsx";
import Icon from "../ui/Icons.jsx";
import Popover from "../ui/Popover.jsx";
import { spring } from "../ui/motion.js";

export const MAX_WEEKS = 20;
const DAY = 86400000;

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

/** Weeks of `year` grouped by the month their Thursday falls in. */
function monthsOf(year) {
  const count = isoWeek(Date.UTC(year, 11, 28))[1];
  const months = Array.from({ length: 12 }, () => []);
  for (let week = 1; week <= count; week++) {
    const monday = mondayOf(year, week);
    months[new Date(monday + 3 * DAY).getUTCMonth()].push({ week, monday, key: weekKey(year, week) });
  }
  return months;
}

function todayUtc() {
  const now = new Date();
  return Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
}

export function WeekPicker({ weeks, active, onChange }) {
  const t = useT();
  const today = todayUtc();
  const [thisYear] = isoWeek(today);
  const latest = weeks.length ? parseWeekKey(weeks[weeks.length - 1])[0] : thisYear;
  const [year, setYear] = useState(latest);
  const months = useMemo(() => monthsOf(year), [year]);
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
    if (next.length > MAX_WEEKS) return;
    if (next.length) onChange(next.sort());
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
          <div className="week-year">
            <button type="button" className="icon-btn" onClick={() => setYear((y) => y - 1)} aria-label={t("ticker.prevYear")}>
              <Icon name="left" size={16} />
            </button>
            <span className="num">{year}</span>
            <button type="button" className="icon-btn" onClick={() => setYear((y) => y + 1)} disabled={year >= thisYear} aria-label={t("ticker.nextYear")}>
              <Icon name="right" size={16} />
            </button>
          </div>
          <div className="week-months">
            {months.map((list, m) => (
              <div key={m} className="week-month">
                <span className="week-month-name">{monthName(Date.UTC(year, m, 15))}</span>
                <div className="week-row">
                  {list.map(({ week, monday, key }) => (
                    <button
                      key={key}
                      type="button"
                      className="week-cell num"
                      aria-pressed={chosen.has(key)}
                      disabled={monday > today}
                      title={`${dayMonth(monday)} – ${dayMonth(monday + 6 * DAY)}`}
                      aria-label={t("ticker.weekLabel", { n: week, from: dayMonth(monday), to: dayMonth(monday + 6 * DAY) })}
                      onClick={(e) => pick(key, e.ctrlKey || e.metaKey, close)}
                    >
                      {week}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <p className="week-hint"><kbd>Ctrl</kbd> + {t("ticker.weekAddHint")}</p>
        </div>
      )}
    </Popover>
  );
}
