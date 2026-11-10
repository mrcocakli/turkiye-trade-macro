"""
Step 2 — turn raw observations into one value per series per month.

    agg = last   last observation in the month (FX, rates, indices)
    agg = mean   average of the month's observations
    agg = sum    sum of the month's observations (flows)

Derived series (config "derived"):
    yoy_pct    (x_t / x_{t-12} - 1) * 100
    diff       a - b
    ratio_pct  a / b * 100

Annual series are stored under December of their year.

Usage:
    python etl/metrics.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import connect, init_db  # noqa: E402

AGG_SQL = {
    "last": """SELECT substr(obs_date,1,7) AS month, value FROM observations o
               WHERE series_id = :sid AND obs_date = (SELECT max(obs_date) FROM observations
                     WHERE series_id = :sid AND substr(obs_date,1,7) = substr(o.obs_date,1,7))""",
    "mean": "SELECT substr(obs_date,1,7) AS month, avg(value) AS value FROM observations WHERE series_id = :sid GROUP BY 1",
    "sum": "SELECT substr(obs_date,1,7) AS month, sum(value) AS value FROM observations WHERE series_id = :sid GROUP BY 1",
}


def prev_year(month):
    return f"{int(month[:4]) - 1}{month[4:]}"


def main():
    conn = connect()
    cfg = init_db(conn)
    conn.execute("DELETE FROM monthly_values")
    for s in cfg["series"]:
        rows = conn.execute(AGG_SQL[s.get("agg", "last")], {"sid": s["id"]}).fetchall()
        conn.executemany("INSERT OR REPLACE INTO monthly_values VALUES (?,?,?)",
                         [(s["id"], r["month"], r["value"] * s.get("scale", 1)) for r in rows])

    def get(sid):
        return dict(conn.execute("SELECT month, value FROM monthly_values WHERE series_id=?", (sid,)).fetchall())

    for d in cfg["derived"]:
        out = {}
        if d["formula"] == "yoy_pct":
            x = get(d["of"])
            out = {m: (v / x[prev_year(m)] - 1) * 100 for m, v in x.items() if x.get(prev_year(m))}
        else:
            a, b = get(d["of"][0]), get(d["of"][1])
            for m in sorted(set(a) & set(b)):
                if d["formula"] == "diff":
                    out[m] = a[m] - b[m]
                elif d["formula"] == "ratio_pct" and b[m]:
                    out[m] = a[m] / b[m] * 100
        conn.executemany("INSERT OR REPLACE INTO monthly_values VALUES (?,?,?)",
                         [(d["id"], m, v) for m, v in out.items()])
    conn.commit()
    n = conn.execute("SELECT count(DISTINCT series_id), count(*) FROM monthly_values").fetchone()
    print(f"monthly_values: {n[0]} series, {n[1]} rows.")


if __name__ == "__main__":
    main()
