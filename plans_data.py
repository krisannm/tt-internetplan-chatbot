"""
plans_data.py
-------------
Loads tt_all_plans.json and answers one question: "what is on sale TODAY?"

Rule: for each plan `id`, take the newest row whose effective_date is today or
earlier. A row dated in the future stays hidden until its day arrives, so you
can add announced price changes ahead of time.
"""
import json
from datetime import datetime, timedelta, timezone

import pandas as pd

DATA_FILE = "tt_all_plans.json"
TT_TZ = timezone(timedelta(hours=-4))  # Trinidad & Tobago is UTC-4 all year (no DST)


def today_tt():
    """Today's date in Trinidad (the Render server runs on UTC)."""
    return pd.Timestamp(datetime.now(TT_TZ).date())


def load_all(path=DATA_FILE):
    with open(path, encoding="utf-8") as f:
        df = pd.DataFrame(json.load(f))
    df["effective_date"] = pd.to_datetime(df["effective_date"])
    df["last_verified"] = pd.to_datetime(df["last_verified"])
    return df


def current_plans(df, as_of=None):
    as_of = pd.Timestamp(as_of) if as_of is not None else today_tt()
    started = df[df["effective_date"] <= as_of]
    newest = started.sort_values("effective_date", kind="stable").groupby("id", sort=False).tail(1)
    newest = newest[newest["status"] == "active"]
    return newest.sort_values(["plan_type", "provider", "price_ttd"]).reset_index(drop=True)


def upcoming_changes(df, as_of=None):
    """Rows that start after `as_of`, with the price they will replace."""
    as_of = pd.Timestamp(as_of) if as_of is not None else today_tt()
    now_price = current_plans(df, as_of).set_index("id")["price_ttd"]
    up = df[df["effective_date"] > as_of].copy()
    up["current_price_ttd"] = up["id"].map(now_price)
    return up.sort_values(["effective_date", "provider", "plan_name"]).reset_index(drop=True)


def history_with_status(df, as_of=None):
    """Every row, labelled Current / Superseded / Upcoming."""
    as_of = pd.Timestamp(as_of) if as_of is not None else today_tt()
    cur = current_plans(df, as_of)
    cur_keys = set(zip(cur["id"], cur["effective_date"]))
    out = df.copy()
    out["status_label"] = [
        "Current" if (i, d) in cur_keys else ("Upcoming" if d > as_of else "Superseded")
        for i, d in zip(out["id"], out["effective_date"])
    ]
    return out.sort_values(["plan_type", "provider", "id", "effective_date"]).reset_index(drop=True)


def to_prompt_records(df):
    """Compact list of dicts for the LLM prompt: dates as text, empty fields dropped."""
    d = df.copy()
    for col in ("effective_date", "last_verified"):
        d[col] = d[col].dt.strftime("%Y-%m-%d")
    d = d.drop(columns=["status"], errors="ignore")
    out = []
    for rec in d.to_dict(orient="records"):
        out.append({k: v for k, v in rec.items() if v is not None and not (isinstance(v, float) and pd.isna(v)) and v != ""})
    return out
