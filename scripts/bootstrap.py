"""One-shot setup: create the schema, import your transactions, warm the caches.

    python scripts/bootstrap.py
    python scripts/bootstrap.py --seed examples/seed_transactions.example.csv
    python scripts/bootstrap.py --reset

With no CSV at `data/seed_transactions.csv` this creates an empty database and stops —
which is what a fresh install wants. Add your holdings in the dashboard, or point
`--seed` at a CSV shaped like `examples/seed_transactions.example.csv`.

Safe to re-run: instrument creation, seed import and split sync are all idempotent.
`--reset` deletes the database file first.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.db import init_db, reset_engine, session_scope  # noqa: E402
from app.services.portfolio import PortfolioService  # noqa: E402
from app.services.seed import DEFAULT_SEED_CSV, import_seed_csv  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
log = logging.getLogger("bootstrap")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="delete the database first")
    parser.add_argument("--skip-refresh", action="store_true", help="do not fetch prices")
    parser.add_argument(
        "--seed",
        type=Path,
        default=None,
        metavar="CSV",
        help=f"transaction CSV to import (default: {DEFAULT_SEED_CSV})",
    )
    args = parser.parse_args()

    if args.seed is not None and not args.seed.exists():
        parser.error(f"no such file: {args.seed}")

    settings = get_settings()

    if args.reset and settings.db_path.exists():
        reset_engine()
        settings.db_path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = settings.db_path.with_name(settings.db_path.name + suffix)
            if sidecar.exists():
                sidecar.unlink()
        log.info("deleted %s", settings.db_path)

    init_db()
    log.info("schema ready at %s", settings.db_path)

    with session_scope() as session:
        report = import_seed_csv(session, settings, args.seed)

    source = args.seed or DEFAULT_SEED_CSV
    print()
    print(f"Seed import ({source if source.exists() else 'no CSV — starting empty'})")
    print(f"  instruments created : {report.instruments_created}")
    print(f"  transactions created: {report.transactions_created}")
    print(f"  already present     : {report.skipped_existing}")

    if report.fx_carried_forward:
        print(f"  FX carried forward  : {len(report.fx_carried_forward)}")
        for note in report.fx_carried_forward:
            print(f"      {note}")
    if report.discrepancies:
        print(f"  total discrepancies : {len(report.discrepancies)}")
        for note in report.discrepancies:
            print(f"      {note}")
    if report.errors:
        print(f"  errors              : {len(report.errors)}")
        for note in report.errors:
            print(f"      {note}")

    if not args.skip_refresh:
        print()
        print("Fetching prices and splits...")
        with session_scope() as session:
            service = PortfolioService(session, settings)
            refresh = service.refresh(force=True)

        print(f"  price rows written  : {refresh.price_rows_written}")
        print(f"  splits found        : {refresh.splits_found}")
        print(f"  splits applied      : {refresh.splits_applied}")
        for ticker, status in sorted(refresh.per_instrument.items()):
            state = "ok" if status.ok else f"FAIL {status.error}"
            close = f"{status.last_close}" if status.last_close is not None else "-"
            traded = status.last_traded.isoformat() if status.last_traded else "-"
            print(f"      {ticker:<6} {close:>12}  last traded {traded}  {status.session:<6} {state}")
        if refresh.errors:
            print(f"  errors              : {len(refresh.errors)}")
            for note in refresh.errors:
                print(f"      {note}")

    print()
    print("Done. Start the server with: make run")
    if report.transactions_created == 0 and not report.skipped_existing:
        print("The portfolio is empty. Add holdings in the dashboard, or bootstrap with")
        print("  python scripts/bootstrap.py --seed examples/seed_transactions.example.csv")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
