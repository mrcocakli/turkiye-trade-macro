"""
One-off seed: copies EVDS series already downloaded for the Mavi treasury
project (USD/TRY, EUR/TRY, deposit, commercial-loan and factoring rates) into
this database, so the dashboard starts with real history before its own first
scheduled run. Same source, same series codes; retrieved_at is preserved.

Usage:
    python etl/seed_from_mavi.py /path/to/mavi_treasury.db
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import connect, init_db  # noqa: E402

QUERIES = {
    "usdtry": "SELECT rate_date, rate, retrieved_at FROM fx_rates WHERE currency_pair='USDTRY' AND rate_type='buying'",
    "eurtry": "SELECT rate_date, rate, retrieved_at FROM fx_rates WHERE currency_pair='EURTRY' AND rate_type='buying'",
    "dep_try_3m": "SELECT period, rate_pct, retrieved_at FROM interest_rates_raw WHERE currency='TRY'",
    "dep_usd_3m": "SELECT period, rate_pct, retrieved_at FROM interest_rates_raw WHERE currency='USD'",
    "loan_try_commercial": "SELECT period, rate_pct, retrieved_at FROM financing_rates_raw WHERE rate_type='commercial_loan'",
    "factoring_try": "SELECT period, rate_pct, retrieved_at FROM financing_rates_raw WHERE rate_type='factoring'",
}


def main():
    src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    conn = connect()
    init_db(conn)
    for sid, q in QUERIES.items():
        rows = [(sid, d, v, r) for d, v, r in src.execute(q) if v is not None]
        conn.executemany("INSERT OR IGNORE INTO observations VALUES (?,?,?,?)", rows)
        last = max(r[1] for r in rows)
        conn.execute("INSERT OR REPLACE INTO series_status VALUES (?,?,?,?,?,?)",
                     (sid, None, "seeded", len(rows), last, "copied from the Mavi treasury database"))
        print(f"{sid:22} {len(rows):5} rows, to {last}")
    conn.commit()


if __name__ == "__main__":
    main()
