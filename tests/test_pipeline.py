"""
Checks on the built database. Run after the pipeline:  python tests/test_pipeline.py
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
conn = sqlite3.connect(ROOT / "db" / "macro.db")
conn.row_factory = sqlite3.Row
passed = failed = 0


def check(label, cond, detail=""):
    global passed, failed
    passed, failed = passed + bool(cond), failed + (not cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


n = conn.execute("SELECT count(*) FROM observations").fetchone()[0]
check("observations loaded", n > 0, f"{n} rows")
dup = conn.execute("SELECT count(*) FROM (SELECT 1 FROM observations GROUP BY series_id, obs_date HAVING count(*)>1)").fetchone()[0]
check("no duplicate (series, date) observations", dup == 0)
bad = conn.execute("SELECT count(*) FROM observations WHERE series_id IN ('usdtry','eurtry') AND value <= 0").fetchone()[0]
check("FX rates are positive", bad == 0)
orphans = conn.execute("SELECT count(*) FROM monthly_values WHERE series_id NOT IN (SELECT series_id FROM series)").fetchone()[0]
check("every monthly value belongs to a catalogued series", orphans == 0)

# Recompute one monthly 'last' value straight from the raw table.
r = conn.execute("SELECT month, value FROM monthly_values WHERE series_id='usdtry' ORDER BY month DESC LIMIT 1").fetchone()
raw = conn.execute("SELECT value FROM observations WHERE series_id='usdtry' AND substr(obs_date,1,7)=? ORDER BY obs_date DESC LIMIT 1", (r["month"],)).fetchone()
check("monthly USD/TRY equals last raw observation of that month", abs(r["value"] - raw["value"]) < 1e-9, f"{r['month']}: {r['value']}")

# The narrative's lead figure must match the database.
nar = conn.execute("SELECT * FROM monthly_narratives ORDER BY month DESC LIMIT 1").fetchone()
check("a narrative exists", nar is not None)
if nar:
    for item in json.loads(nar["body_json"])["items"]:
        v = conn.execute("SELECT value FROM monthly_values WHERE series_id=? AND month=?", (item["series_id"], item["month"])).fetchone()
        if v is None or abs(v["value"] - item["value"]) > 1e-9:
            check(f"narrative value for {item['series_id']} matches monthly_values", False)
            break
    else:
        check("every narrative value matches monthly_values", True)
    check("narrative report file exists", (ROOT / "reports" / f"what-changed-{nar['month']}.md").exists())

v = conn.execute("SELECT count(*) FROM v_latest").fetchone()[0]
check("v_latest view returns rows", v > 0, f"{v} series")
html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
check("page has data embedded", "/*__DATA__*/null" not in html and '"series"' in html)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
