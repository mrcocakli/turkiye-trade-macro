"""
Step 1 — pull every configured series and upsert it into `observations`.

Each series is fetched on its own, so one bad code or one source outage does
not stop the others. The outcome per series is written to `series_status`
and summarised in reports/pipeline_status.md, which the scheduled run commits.

Usage:
    python etl/load.py [--years 6]
"""
import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, connect, init_db  # noqa: E402
from sources import FETCHERS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=6, help="history window to (re)load")
    args = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    conn = connect()
    cfg = init_db(conn)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    end = date.today()
    start = date(end.year - args.years, 1, 1)
    run_id = conn.execute("INSERT INTO pipeline_runs (started_at) VALUES (?)", (now,)).lastrowid
    ok = failed = 0
    for s in cfg["series"]:
        try:
            rows = FETCHERS[s["source"]](s["code"], start.isoformat(), end.isoformat())
            if not rows:
                raise RuntimeError("source returned no rows")
            conn.executemany(
                """INSERT INTO observations (series_id, obs_date, value, retrieved_at) VALUES (?,?,?,?)
                   ON CONFLICT(series_id, obs_date) DO UPDATE SET value=excluded.value,
                       retrieved_at=excluded.retrieved_at""",
                [(s["id"], d, v, now) for d, v in rows])
            status, msg, n, last = "ok", "", len(rows), rows[-1][0]
            ok += 1
        except Exception as e:  # noqa: BLE001 — record and carry on with the other series
            prev = conn.execute("SELECT max(obs_date) FROM observations WHERE series_id=?", (s["id"],)).fetchone()[0]
            status, msg, n, last = "failed", f"{type(e).__name__}: {e}"[:300], 0, prev
            failed += 1
        conn.execute("INSERT OR REPLACE INTO series_status VALUES (?,?,?,?,?,?)",
                     (s["id"], run_id, status, n, last, msg))
        print(f"[{status:6}] {s['id']:22} {s['code']:24} rows={n:5} last={last} {msg}")
    conn.execute("UPDATE pipeline_runs SET finished_at=?, series_ok=?, series_failed=? WHERE run_id=?",
                 (datetime.now(timezone.utc).isoformat(timespec="seconds"), ok, failed, run_id))
    conn.commit()
    write_status_report(conn)
    print(f"\nLoaded {ok} series, {failed} failed.")
    # Fail the run only if nothing at all loaded; partial failures are reported, not fatal.
    sys.exit(1 if ok == 0 else 0)


def write_status_report(conn):
    rows = conn.execute(
        """SELECT s.series_id, s.source_id, s.source_code, st.status, st.rows_loaded, st.last_obs, st.message
           FROM series s LEFT JOIN series_status st USING (series_id)
           WHERE s.is_derived = 0 ORDER BY s.sort_order""").fetchall()
    run = conn.execute("SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT 1").fetchone()
    lines = ["# Pipeline status", "",
             f"Last run started {run['started_at']} UTC: {run['series_ok']} series loaded, "
             f"{run['series_failed']} failed.", "",
             "| Series | Source | Code | Status | Rows | Latest observation | Message |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['series_id']} | {r['source_id']} | `{r['source_code']}` | {r['status'] or 'never run'} | "
                     f"{r['rows_loaded'] if r['rows_loaded'] is not None else ''} | {r['last_obs'] or ''} | {r['message'] or ''} |")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "pipeline_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
