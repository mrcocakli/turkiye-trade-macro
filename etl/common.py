"""Shared helpers: paths, config and database connection."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "macro.db"
CONFIG_PATH = ROOT / "config" / "series.json"

SOURCES = [
    ("evds", "TCMB EVDS (Central Bank of the Republic of Türkiye)", "https://evds3.tcmb.gov.tr"),
    ("worldbank", "World Bank Open Data", "https://data.worldbank.org/country/turkiye"),
]

PP_UNITS = {"%", "pp", "% of GDP"}   # changes in these are quoted in percentage points


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    """Create tables/views and sync the series catalogue from config/series.json."""
    conn.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    conn.executemany("INSERT OR REPLACE INTO sources VALUES (?,?,?)", SOURCES)
    cfg = load_config()
    order = 0
    for s in cfg["series"]:
        order += 1
        conn.execute(
            """INSERT INTO series (series_id, source_id, source_code, name, unit, category, freq, agg,
                                   decimals, good_when, is_derived, sort_order)
               VALUES (?,?,?,?,?,?,?,?,?,?,0,?)
               ON CONFLICT(series_id) DO UPDATE SET source_id=excluded.source_id,
                   source_code=excluded.source_code, name=excluded.name, unit=excluded.unit,
                   category=excluded.category, freq=excluded.freq, agg=excluded.agg,
                   decimals=excluded.decimals, good_when=excluded.good_when, sort_order=excluded.sort_order""",
            (s["id"], s["source"], s["code"], s["name"], s["unit"], s["category"], s.get("freq", "M"),
             s.get("agg", "last"), s.get("decimals", 1), s.get("good_when"), order))
    for d in cfg["derived"]:
        order += 1
        conn.execute(
            """INSERT INTO series (series_id, source_id, source_code, name, unit, category, freq, agg,
                                   decimals, good_when, is_derived, sort_order)
               VALUES (?,NULL,NULL,?,?,?,'M','last',?,?,1,?)
               ON CONFLICT(series_id) DO UPDATE SET name=excluded.name, unit=excluded.unit,
                   category=excluded.category, decimals=excluded.decimals, good_when=excluded.good_when,
                   sort_order=excluded.sort_order""",
            (d["id"], d["name"], d["unit"], d["category"], d.get("decimals", 1), d.get("good_when"), order))
    conn.commit()
    return cfg
