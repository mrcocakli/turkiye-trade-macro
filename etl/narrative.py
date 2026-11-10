"""
Step 3 — "What changed this month", written by rules, not by hand.

For every monthly series the latest month is compared with the month before:
    change      percentage points for rates/ratios, per cent for levels
    typical     median absolute value of the same change over the prior 24 months
    z           |change| / typical  -> how unusual the move is for that series
Series are ranked by z, so the narrative leads with what is unusual rather
than with what is merely large. The wording is templated, so the same data
always produces the same text, and every sentence can be traced to
monthly_values.

Output: a row in monthly_narratives and reports/what-changed-YYYY-MM.md.

Usage:
    python etl/narrative.py
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PP_UNITS, ROOT, connect, init_db  # noqa: E402

STALE_MONTHS = 4
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month_label(m):
    return f"{MONTHS[int(m[5:7]) - 1]} {m[:4]}"


def fmt(v, decimals):
    return f"{v:,.{decimals}f}"


def unit_suffix(unit):
    return "%" if unit == "%" else f" {unit}" if unit in ("pp", "% of GDP", "USD bn") else ""


def describe(conn, s):
    """Return the change record for one series, or None if it has fewer than two months."""
    rows = conn.execute("SELECT month, value FROM monthly_values WHERE series_id=? ORDER BY month",
                        (s["series_id"],)).fetchall()
    if len(rows) < 2:
        return None
    vals = [r["value"] for r in rows]
    # Rates and ratios move in percentage points. A series that can be zero or negative
    # (a trade balance) moves in its own unit, because a per cent change on a negative
    # base reads backwards. Everything else moves in per cent.
    is_pp = s["unit"] in PP_UNITS or min(vals) <= 0
    chg_unit = "pp" if s["unit"] in PP_UNITS else (s["unit"] if is_pp else "%")
    sfx = "%" if chg_unit == "%" else f" {chg_unit}"
    chg = [(b - a) if is_pp else ((b / a - 1) * 100 if a else 0.0) for a, b in zip(vals, vals[1:])]
    cur, hist = chg[-1], chg[-25:-1]
    typical = statistics.median(abs(c) for c in hist) if len(hist) >= 6 else None
    z = abs(cur) / typical if typical else None
    month, value = rows[-1]["month"], vals[-1]
    yago = dict((r["month"], r["value"]) for r in rows).get(f"{int(month[:4]) - 1}{month[4:]}")
    yoy = None if yago is None else ((value - yago) if is_pp else ((value / yago - 1) * 100 if yago else None))

    d, unit_word = s["decimals"], chg_unit
    small = abs(cur) < (0.05 if is_pp else 0.05)
    verb = "was unchanged" if small else ("rose" if cur > 0 else "fell")
    size = "" if z is None or z < 1.5 else (", an unusually large move for this series" if z >= 3
                                            else ", a larger move than usual")
    # Daily series: say which day the month's reading is from, so a part-month is never read as a full one.
    n_obs, last_obs = conn.execute(
        "SELECT count(*), max(obs_date) FROM observations WHERE series_id=? AND substr(obs_date,1,7)=?",
        (s["series_id"], month)).fetchone()
    when = (f"on {int(last_obs[8:10])} {month_label(month)}" if n_obs and n_obs > 1 else f"in {month_label(month)}")
    amount = "" if small else f" {abs(cur):.{1 if chg_unit in ('%', 'pp') else d}f}{sfx}"
    sentence = (f"{s['name']} {verb}{amount} {'at' if small else 'to'} {fmt(value, d)}{unit_suffix(s['unit'])} {when}"
                f"{size}.")
    if yoy is not None and abs(yoy) < 0.05:
        sentence += " It is unchanged on a year earlier."
    elif yoy is not None:
        sentence += (f" It is {'up' if yoy > 0 else 'down'} {abs(yoy):.{1 if chg_unit in ('%', 'pp') else d}f}{sfx} on a year earlier.")
    tone = "neutral"
    if s["good_when"] and not small:
        tone = "favourable" if (cur > 0) == (s["good_when"] == "up") else "unfavourable"
    return {"series_id": s["series_id"], "name": s["name"], "category": s["category"], "month": month,
            "value": value, "prev_value": vals[-2], "change": cur, "change_unit": unit_word,
            "typical": typical, "z": z, "last_obs": last_obs, "when": when, "yoy": yoy, "tone": tone, "sentence": sentence}


def main():
    conn = connect()
    init_db(conn)
    series = conn.execute("SELECT * FROM series WHERE freq='M' ORDER BY sort_order").fetchall()
    items = [x for x in (describe(conn, s) for s in series) if x]
    if not items:
        print("No series with two months of data yet; no narrative written.")
        return
    edition = max(x["month"] for x in items)
    # A series whose latest month is more than STALE_MONTHS behind the edition has
    # stopped updating at the source; it is reported as stale, not as news.
    def months_behind(m):
        return (int(edition[:4]) - int(m[:4])) * 12 + int(edition[5:7]) - int(m[5:7])
    stale = [x for x in items if months_behind(x["month"]) > STALE_MONTHS]
    items = [x for x in items if months_behind(x["month"]) <= STALE_MONTHS]
    # Lead with the most unusual moves; series without enough history for a z-score go last.
    items.sort(key=lambda x: (x["z"] is None, -(x["z"] or 0)))
    fresh = [x for x in items if x["month"] == edition]
    lead = fresh[0] if fresh else items[0]
    ups = sum(1 for x in fresh if x["change"] > 0.05)
    downs = sum(1 for x in fresh if x["change"] < -0.05)
    direction = "rose" if lead["change"] > 0 else "fell"
    headline = (f"{lead['name']} {direction} {abs(lead['change']):.1f}"
                f"{'%' if lead['change_unit'] == '%' else ' ' + lead['change_unit']} {lead['when'].replace('on ', 'by ', 1)}")
    summary = (f"Of {len(fresh)} series with {month_label(edition)} data, {ups} rose and {downs} fell. "
               f"{len(items) - len(fresh)} more are shown at their latest available month."
               + (f" {len(stale)} stopped updating at the source and are left out." if stale else ""))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = {"edition": edition, "summary": summary, "items": items,
            "stale": [x["series_id"] for x in stale]}
    conn.execute("INSERT OR REPLACE INTO monthly_narratives VALUES (?,?,?,?)",
                 (edition, now, headline, json.dumps(body)))
    conn.commit()

    md = [f"# What changed: {month_label(edition)}", "", f"**{headline}.** {summary}", "",
          "Ranked by how unusual each move is against the series' own last 24 months.", ""]
    for i, x in enumerate(items, 1):
        z = "n/a" if x["z"] is None else f"{x['z']:.1f}x its typical monthly move"
        md.append(f"{i}. {x['sentence']} ({z})")
    md += ["", f"Generated {now} UTC by etl/narrative.py from db/macro.db. Rule-based text; no figures are typed by hand."]
    (ROOT / "reports").mkdir(exist_ok=True)
    out = ROOT / "reports" / f"what-changed-{edition}.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Narrative for {edition}: {headline}. -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
