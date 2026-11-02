"""Shared helpers: paths, config loading, data loading, small math utilities."""
from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "model_config.yaml"
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
SITE = ROOT / "site"

RATING_ORDER = ["Safe D", "Likely D", "Lean D", "Tilt D", "Toss-up", "Tilt R", "Lean R", "Likely R", "Safe R"]

# processed-file race codes -> model race names
RACES = {"pres2024": "pres_2024", "gov2024": "gov_2024", "gov2022": "gov_2022", "ussen2022": "sen_2022",
         "pres2020": "pres_2020", "cong2022": "cong_2022", "cong2024": "cong_2024"}


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def read_csv(name: str, **kw) -> pd.DataFrame | None:
    p = PROCESSED / name
    if not p.exists():
        return None
    return pd.read_csv(p, **kw)


def to_date(x) -> date | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    if isinstance(x, date):
        return x
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


def two_party_margin(dem, rep) -> float:
    dem = float(dem or 0); rep = float(rep or 0)
    tot = dem + rep
    if tot <= 0:
        return float("nan")
    return 100.0 * (dem - rep) / tot


def prob_from_margin(mu: float, sd: float) -> float:
    return float(norm.cdf(mu / sd))


def margin_from_prob(p: float, sd: float) -> float:
    p = min(max(p, 0.001), 0.999)
    return float(norm.ppf(p) * sd)


def rating_from_prob(p: float) -> str:
    if p >= 0.95: return "Safe D"
    if p >= 0.80: return "Likely D"
    if p >= 0.65: return "Lean D"
    if p >= 0.55: return "Tilt D"
    if p > 0.45: return "Toss-up"
    if p > 0.35: return "Tilt R"
    if p > 0.20: return "Lean R"
    if p > 0.05: return "Likely R"
    return "Safe R"


def dump_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

    def default(o):
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.bool_,)): return bool(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(o)
        if isinstance(o, (np.ndarray,)): return o.tolist()
        if isinstance(o, (date, datetime)): return o.isoformat()
        if isinstance(o, float) and math.isnan(o): return None
        return str(o)
    with open(path, "w") as f:
        json.dump(obj, f, default=default, indent=None, separators=(",", ":"))


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def load_districts() -> pd.DataFrame:
    d = read_csv("districts.csv")
    d["floterial"] = d["floterial"].map(truthy)
    return d


def load_baseline() -> tuple[pd.DataFrame, dict]:
    """Wide table keyed by (chamber, key) with <race>_margin columns, and statewide margins
    computed from the Senate districts (which partition the state)."""
    b = read_csv("district_baseline.csv")
    b["race"] = b["race"].map(RACES).fillna(b["race"])
    b["margin"] = [two_party_margin(d, r) for d, r in zip(b["dem"], b["rep"])]
    wide = b.pivot_table(index=["chamber", "key"], columns="race", values="margin", aggfunc="first")
    wide.columns = [f"{c}_margin" for c in wide.columns]
    wide = wide.reset_index()
    statewide = {}
    sen = b[b["chamber"] == "senate"]
    for race, sub in sen.groupby("race"):
        statewide[race] = two_party_margin(sub["dem"].sum(), sub["rep"].sum())
    return wide, statewide


def load_results() -> tuple[pd.DataFrame, pd.DataFrame]:
    """District-level legislative results and candidate rows, with numeric types."""
    res = read_csv("legislative_results.csv")
    res["contested"] = res["contested"].map(truthy)
    for c in ("seats", "n_d", "n_r", "n_other", "d_votes", "r_votes", "other_votes", "d_seats", "r_seats", "other_seats", "inc_d_running", "inc_r_running"):
        res[c] = pd.to_numeric(res[c], errors="coerce").fillna(0).astype(int)
    res["party_margin"] = pd.to_numeric(res["party_margin"], errors="coerce")
    cands = read_csv("legislative_candidates.csv")
    cands["won"] = cands["won"].map(truthy); cands["incumbent_pre"] = cands["incumbent_pre"].map(truthy)
    cands["votes"] = pd.to_numeric(cands["votes"], errors="coerce")
    return res, cands


def load_candidates_2026() -> pd.DataFrame:
    c = read_csv("candidates_2026.csv")
    c["incumbent"] = c["incumbent"].map(truthy)
    c["also_dem"] = c["also_dem"].map(truthy); c["also_rep"] = c["also_rep"].map(truthy)
    c["note"] = c["note"].fillna("")
    c["other_label"] = c["other_label"].fillna("")
    return c
