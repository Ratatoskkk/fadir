// What the company behind the charted symbol does: its sector and industry, Yahoo's
// business summary and a few facts. Beside the chart on a wide screen, under it on a narrow one.

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../../api.js";
import { compact, num } from "../../format.js";
import { useT } from "../i18n/index.jsx";
import Icon from "../ui/Icons.jsx";

/** "https://www.apple.com/" → "apple.com". */
const hostOf = (url) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
};

function useProfile(symbol) {
  const [state, setState] = useState({ symbol: null, data: null, error: null });
  const asked = useRef(symbol);
  asked.current = symbol;
  const load = useCallback(async () => {
    setState({ symbol: null, data: null, error: null });
    try {
      const data = await api.marketProfile(symbol);
      if (asked.current === symbol) setState({ symbol, data, error: null });
    } catch (error) {
      if (asked.current === symbol) setState({ symbol, data: null, error });
    }
  }, [symbol]);
  useEffect(() => { load(); }, [load]);
  const fresh = state.symbol === symbol;
  return { data: fresh ? state.data : null, error: fresh ? state.error : null, loading: !fresh, reload: load };
}

export default function CompanyInfo({ symbol }) {
  const t = useT();
  const { data, error, loading, reload } = useProfile(symbol);
  const [expanded, setExpanded] = useState(false);
  const [clamped, setClamped] = useState(false);
  const summaryRef = useRef(null);
  useEffect(() => { setExpanded(false); }, [symbol]);
  // "More" only when the clamp actually hides something.
  useLayoutEffect(() => {
    const el = summaryRef.current;
    if (!el || expanded) return undefined;
    const measure = () => setClamped(el.scrollHeight > el.clientHeight + 1);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [data, expanded]);

  // Nothing to say beyond the type (an index, a future, an unknown symbol): no panel,
  // and the chart takes the width.
  if (error?.status === 404 || (data && !data.summary && !data.sector && !data.category)) return null;

  const place = data ? [data.city, data.country].filter(Boolean).join(", ") : "";
  // Funds have a category and a family; companies a sector and an industry.
  const facts = data ? [
    ...(data.sector ? [["ticker.info.sector", data.sector]] : []),
    ...(data.industry ? [["ticker.info.industry", data.industry]] : []),
    ...(data.category ? [["ticker.info.category", data.category]] : []),
    ...(data.fund_family ? [["ticker.info.fundFamily", data.fund_family]] : []),
    ...(!data.sector && !data.category && data.kind ? [["ticker.info.kind", data.kind]] : []),
    ...(place ? [["ticker.info.hq", place]] : []),
    ...(data.employees ? [["ticker.info.employees", num(data.employees, 0)]] : []),
    ...(data.market_cap ? [["ticker.info.marketCap", `${compact(data.market_cap)} ${data.currency ?? ""}`.trim()]] : []),
  ] : [];

  return (
    <aside className={`card ticker-info ${expanded ? "expanded" : ""}`} aria-labelledby="ticker-info-title">
      <header className="card-head">
        <h2 id="ticker-info-title">{t("ticker.info.title")}</h2>
      </header>
      {loading ? (
        <div className="info-skeleton" aria-hidden="true"><i /><i /><i /><i /></div>
      ) : error ? (
        <div className="info-empty">
          <p className="muted">{t("ticker.info.failed")}</p>
          <button type="button" className="btn small" onClick={reload}><Icon name="refresh" size={14} /> {t("common.retry")}</button>
        </div>
      ) : (
        <>
          {facts.length > 0 && (
            <dl className="info-facts">
              {facts.map(([label, value]) => (
                <div key={label}><dt>{t(label)}</dt><dd>{value}</dd></div>
              ))}
            </dl>
          )}
          {data.summary && (
            <div className="info-summary-wrap">
              {/* Yahoo writes summaries in English, whatever the page's language. */}
              <p ref={summaryRef} id="ticker-info-summary" lang="en" className={`info-summary ${expanded ? "" : "clamped"}`}>{data.summary}</p>
              {(clamped || expanded) && (
                <button type="button" className="info-more" aria-expanded={expanded} aria-controls="ticker-info-summary" onClick={() => setExpanded((v) => !v)}>
                  {t(expanded ? "ticker.info.less" : "ticker.info.more")}
                </button>
              )}
            </div>
          )}
          {data.website && (
            <a className="info-link" href={data.website} target="_blank" rel="noopener noreferrer">
              <Icon name="globe" size={14} />{hostOf(data.website)}
              <span className="sr-only">{t("common.newTab")}</span>
            </a>
          )}
        </>
      )}
    </aside>
  );
}
