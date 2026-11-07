export default function PortfolioSelector({ portfolios, selectedId, loading, onChange }) {
  const hasPortfolios = portfolios.length > 0;

  return (
    <section className="portfolio-selector" aria-labelledby="portfolio-selector-title">
      <div>
        <strong id="portfolio-selector-title">Portföy</strong>
        {hasPortfolios ? (
          <span className="portfolio-selector-hint">Çalışma alanınızdaki portföyü seçin.</span>
        ) : (
          <span className="portfolio-selector-hint">
            Henüz Portföy yok. İlk geçerli işlem kaydedildiğinde Ana Portföy oluşturulur.
          </span>
        )}
      </div>
      {hasPortfolios && (
        <label className="portfolio-selector-field" htmlFor="portfolio-selector">
          <span className="sr-only">Portföy seçin</span>
          <select
            id="portfolio-selector"
            value={selectedId ?? ""}
            onChange={(event) => onChange(Number(event.target.value))}
            disabled={loading}
          >
            {portfolios.map((portfolio) => (
              <option key={portfolio.id} value={portfolio.id}>
                {portfolio.name} · {portfolio.base_currency}
              </option>
            ))}
          </select>
        </label>
      )}
      {loading && <span className="portfolio-selector-status" role="status" aria-live="polite">yükleniyor…</span>}
    </section>
  );
}
