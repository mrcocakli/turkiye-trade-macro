"""
Helper — lists EVDS data groups and series whose names match a keyword, so a
replacement code can be found when a series is discontinued (as the 2003=100
CPI was in January 2026). Writes reports/evds_discovery.md.

Usage:
    python etl/discover.py "TÜKETİCİ" "CONSUMER" "TÜFE"
"""
import os
import sys
from pathlib import Path

import pandas as pd
import tcmb

ROOT = Path(__file__).resolve().parent.parent


def matches(row, words):
    text = " ".join(str(v) for v in row.values).upper()
    return any(w.upper() in text for w in words)


def main():
    words = sys.argv[1:] or ["TÜKETİCİ", "CONSUMER", "TÜFE", "CPI"]
    client = tcmb.Client(api_key=os.environ["EVDS_API_KEY"])
    out = [f"# EVDS discovery for: {', '.join(words)}", ""]
    groups = client.get_datagroups_metadata()
    hit = groups[groups.apply(lambda r: matches(r, words), axis=1)]
    out += [f"{len(hit)} of {len(groups)} data groups matched. Columns: {list(groups.columns)}", ""]
    code_col = next((c for c in groups.columns if "DATAGROUP_CODE" in c.upper()), groups.columns[0])
    for _, g in hit.head(25).iterrows():
        out += [f"## {g[code_col]}", "", "```", g.to_string(), "```", ""]
        try:
            series = pd.DataFrame(client.get_series_metadata(datagroup=str(g[code_col])))
            keep = [c for c in series.columns if any(k in c.upper() for k in ("SERIE_CODE", "SERIE_NAME", "START_DATE", "END_DATE", "FREQUENCY"))]
            out += ["```", series[keep or series.columns].head(40).to_string(), "```", ""]
        except Exception as e:  # noqa: BLE001
            out += [f"(could not list series: {type(e).__name__}: {e})", ""]
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "evds_discovery.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote reports/evds_discovery.md ({len(hit)} groups).")


if __name__ == "__main__":
    main()
