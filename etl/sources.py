"""Source adapters. Each returns a list of (iso_date, float_value) for one series."""
import os

import pandas as pd
import requests


def fetch_evds(code: str, start: str, end: str):
    """TCMB EVDS through the `tcmb` package (tracks the evds3 endpoint).

    tcmb.read returns a DataFrame indexed by date with one column per series;
    reset_index() immediately and filter dates client-side, because the
    start-date parameter is not reliably honoured server-side.
    """
    import tcmb  # imported lazily so offline steps do not need the package

    key = os.getenv("EVDS_API_KEY")
    if not key:
        raise RuntimeError("EVDS_API_KEY is not set")
    df = tcmb.read([code], start=start, end=end, api_key=key).reset_index()
    date_col, val_col = df.columns[0], df.columns[-1]
    df[date_col] = pd.to_datetime(df[date_col].astype(str), errors="coerce")
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    df = df.dropna(subset=[date_col, val_col])
    df = df[(df[date_col] >= pd.Timestamp(start)) & (df[date_col] <= pd.Timestamp(end))]
    return [(d.date().isoformat(), float(v)) for d, v in zip(df[date_col], df[val_col])]


def fetch_worldbank(code: str, start: str, end: str, country: str = "TUR"):
    """World Bank Open Data API v2 (no key). Annual values, dated 31 December."""
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{code}"
    r = requests.get(url, params={"format": "json", "per_page": 200,
                                  "date": f"{start[:4]}:{end[:4]}"}, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        raise RuntimeError(f"Unexpected World Bank response for {code}: {str(payload)[:200]}")
    return sorted((f"{row['date']}-12-31", float(row["value"]))
                  for row in payload[1] if row.get("value") is not None)


FETCHERS = {"evds": fetch_evds, "worldbank": fetch_worldbank}
