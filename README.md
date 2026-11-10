# Türkiye Trade & Macro Monitor

A self-updating monitor of Türkiye's exchange rates, interest rates, prices and trade, built from free public data: Python pipelines into a SQL schema, a rule-based "what changed this month" narrative, and a single flagship page.

**Live page:** `docs/index.html` (served by GitHub Pages once enabled)

## How it works

```
config/series.json  ->  etl/load.py  ->  observations        raw, long format, as published
                        etl/metrics.py -> monthly_values      one value per series per month + derived series
                        etl/narrative.py -> monthly_narratives + reports/what-changed-YYYY-MM.md
                        etl/build_page.py -> docs/index.html
```

`python run_pipeline.py` runs all four steps. `python run_pipeline.py --offline` skips the download and rebuilds from the database. `python tests/test_pipeline.py` checks the result.

| Piece | Where |
|---|---|
| SQL schema (tables + `v_latest` view) | `db/schema.sql` |
| Series catalogue: one JSON line per series | `config/series.json` |
| Source adapters (TCMB EVDS, World Bank) | `etl/sources.py` |
| Narrative rules | `etl/narrative.py` |
| Page template | `web/template.html` |
| Monthly schedule | `.github/workflows/monthly-refresh.yml` |

## The "what changed" narrative

For each monthly series the latest month is compared with the month before. The change (percentage points for rates, per cent for levels) is divided by that series' median absolute monthly change over the previous 24 months. Series are ranked by that ratio, so the page leads with what is unusual rather than what is merely large. The wording is templated: the same data always yields the same text, and a test confirms every quoted value matches the database.

## Data status

Six EVDS series (USD/TRY, EUR/TRY, deposit, commercial-loan and factoring rates) carry real history, seeded from the companion [Mavi treasury simulation](https://github.com/mrcocakli/mavi_financial_simulation) database. The remaining EVDS codes in `config/series.json` (funding cost, CPI, exports, imports) and the World Bank series are marked `"verified": false` or are pending until the first scheduled run; `reports/pipeline_status.md` then records exactly which codes loaded. A code that fails is reported there and on the page, and does not stop the others.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # add your free EVDS key
python run_pipeline.py
```

For the monthly automation add the repository secret `EVDS_API_KEY` and enable GitHub Pages from `main` / `docs`.

## Sources

TCMB EVDS (Central Bank of the Republic of Türkiye) and World Bank Open Data. No paid or private data. This is a monitoring project, not a forecast or investment advice.
