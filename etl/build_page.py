"""
Step 4 — build the flagship page (docs/index.html) from the database.

A single self-contained HTML file: the template in web/template.html with the
data embedded as JSON. docs/ is what GitHub Pages serves.

Usage:
    python etl/build_page.py
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, connect, init_db  # noqa: E402

MARKER = "/*__DATA__*/null"
REPO_URL = ""   # set to the GitHub URL once the repository exists
STATUS_TEXT = {"ok": "Loaded", "seeded": "Loaded (seed)", "failed": "Last pull failed", None: "Awaiting first run"}


def main():
    conn = connect()
    init_db(conn)
    src_name = {r["source_id"]: r["name"].split(" (")[0] for r in conn.execute("SELECT * FROM sources")}
    series = []
    for s in conn.execute("""SELECT s.*, st.status, st.last_obs FROM series s
                             LEFT JOIN series_status st USING (series_id) ORDER BY s.sort_order"""):
        limit = 15 if s["freq"] == "A" else 36
        hist = conn.execute("SELECT month, value FROM monthly_values WHERE series_id=? ORDER BY month DESC LIMIT ?",
                            (s["series_id"], limit)).fetchall()[::-1]
        per_month = conn.execute("""SELECT max(c) FROM (SELECT count(*) c FROM observations
                                    WHERE series_id=? GROUP BY substr(obs_date,1,7))""", (s["series_id"],)).fetchone()[0]
        if s["is_derived"]:
            status = "Calculated" if hist else "Awaiting inputs"
        else:
            status = STATUS_TEXT.get(s["status"], s["status"])
            if s["status"] == "failed" and hist:
                status = "Loaded (last pull failed)"
        series.append({
            "id": s["series_id"], "name": s["name"], "unit": s["unit"], "category": s["category"],
            "freq": s["freq"], "decimals": s["decimals"], "good_when": s["good_when"],
            "source": src_name.get(s["source_id"], "Calculated from loaded series"),
            "code": s["source_code"], "status": status, "last_obs": s["last_obs"],
            "daily": bool(per_month and per_month > 1),
            "history": [[r["month"], round(r["value"], 6)] for r in hist],
        })
    n = conn.execute("SELECT * FROM monthly_narratives ORDER BY month DESC LIMIT 1").fetchone()
    narrative = None
    if n:
        body = json.loads(n["body_json"])
        narrative = {"edition": n["month"], "headline": n["headline"], "summary": body["summary"], "items": body["items"]}
    data = {"generated": date.today().isoformat(), "repo": REPO_URL, "series": series, "narrative": narrative}
    html = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
    if MARKER not in html:
        sys.exit("Template marker not found.")
    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html.replace(MARKER, json.dumps(data)), encoding="utf-8")
    loaded = sum(1 for s in series if s["history"])
    print(f"Wrote {out.relative_to(ROOT)}: {loaded} of {len(series)} series with data.")


if __name__ == "__main__":
    main()
