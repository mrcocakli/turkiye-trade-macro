-- Türkiye trade & macro dashboard — SQLite schema.
-- Raw observations are stored exactly as the source returned them (long format);
-- everything the page shows is derived from them in SQL views or in etl/metrics.py.

CREATE TABLE IF NOT EXISTS sources (
    source_id   TEXT PRIMARY KEY,          -- 'evds', 'worldbank'
    name        TEXT NOT NULL,
    url         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS series (
    series_id   TEXT PRIMARY KEY,          -- short id from config/series.json
    source_id   TEXT REFERENCES sources(source_id),   -- NULL for derived series
    source_code TEXT,                      -- e.g. 'TP.DK.USD.A.YTL'
    name        TEXT NOT NULL,
    unit        TEXT NOT NULL,
    category    TEXT NOT NULL,
    freq        TEXT NOT NULL DEFAULT 'M', -- display frequency: M or A
    agg         TEXT NOT NULL DEFAULT 'last',  -- how daily data becomes monthly: last | mean | sum
    decimals    INTEGER NOT NULL DEFAULT 1,
    good_when   TEXT,                      -- 'up' | 'down' | NULL
    is_derived  INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS observations (
    series_id    TEXT NOT NULL REFERENCES series(series_id),
    obs_date     TEXT NOT NULL,            -- ISO date as published by the source
    value        REAL NOT NULL,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (series_id, obs_date)
);

-- One row per series per month, after aggregation and derivations.
CREATE TABLE IF NOT EXISTS monthly_values (
    series_id TEXT NOT NULL REFERENCES series(series_id),
    month     TEXT NOT NULL,               -- 'YYYY-MM'
    value     REAL NOT NULL,
    PRIMARY KEY (series_id, month)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    series_ok   INTEGER,
    series_failed INTEGER
);

CREATE TABLE IF NOT EXISTS series_status (
    series_id   TEXT PRIMARY KEY REFERENCES series(series_id),
    last_run_id INTEGER REFERENCES pipeline_runs(run_id),
    status      TEXT NOT NULL,             -- 'ok' | 'failed' | 'seeded'
    rows_loaded INTEGER,
    last_obs    TEXT,
    message     TEXT
);

CREATE TABLE IF NOT EXISTS monthly_narratives (
    month        TEXT PRIMARY KEY,         -- the reference month the narrative describes
    generated_at TEXT NOT NULL,
    headline     TEXT NOT NULL,
    body_json    TEXT NOT NULL             -- ordered list of {series_id, sentence, ...}
);

-- Latest month, previous month and year-ago value for every series.
CREATE VIEW IF NOT EXISTS v_latest AS
WITH ranked AS (
    SELECT series_id, month, value,
           ROW_NUMBER() OVER (PARTITION BY series_id ORDER BY month DESC) AS rn
    FROM monthly_values
)
SELECT s.series_id, s.name, s.unit, s.category, s.freq, s.decimals, s.good_when, s.sort_order,
       cur.month  AS month,      cur.value  AS value,
       prev.month AS prev_month, prev.value AS prev_value,
       yago.value AS year_ago_value
FROM series s
JOIN ranked cur ON cur.series_id = s.series_id AND cur.rn = 1
LEFT JOIN ranked prev ON prev.series_id = s.series_id AND prev.rn = 2
LEFT JOIN monthly_values yago
       ON yago.series_id = s.series_id
      AND yago.month = strftime('%Y-%m', date(cur.month || '-01', '-12 months'));
