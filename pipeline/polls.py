"""Poll averaging used for the statewide environment and for district polls.

A single weighted-average routine implements the config's recency,
sample-size, pollster-rating, partisan-sponsorship and same-pollster
rules. It returns the average, an effective sample size, and the
per-poll weights so the site can show exactly how each poll counted.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .common import to_date


def _grade_multiplier(grade, cfg_mult: dict) -> float:
    if grade is None or (isinstance(grade, float) and np.isnan(grade)) or str(grade).strip() == "":
        return cfg_mult.get("unrated", 0.65)
    g = str(grade).strip()
    if g in cfg_mult:
        return cfg_mult[g]
    # numeric score (e.g. Silver Bulletin 0-3 stars or 0-100): map coarsely
    try:
        v = float(g)
        if v <= 3.0:        # star-ish scale
            return 0.6 + 0.25 * v
        return 0.4 + 0.9 * (v / 100.0)
    except ValueError:
        return cfg_mult.get("unrated", 0.65)


def weighted_poll_average(polls: pd.DataFrame, as_of: date, cfg: dict,
                          ratings: pd.DataFrame | None = None,
                          value_col: str = "margin_dem",
                          internal_col: str | None = None,
                          internal_mult: float | None = None,
                          internal_bias: float | None = None) -> dict:
    """Return {'mean','n_eff','n_polls','weights': DataFrame} for polls.

    cfg is the `environment.polls` (or `district_polls`) config block.
    Partisan sponsorship uses sponsor_party in (D, R). Bias corrections
    push the value AGAINST the sponsor.
    """
    if polls is None or len(polls) == 0:
        return {"mean": np.nan, "n_eff": 0.0, "n_polls": 0, "weights": pd.DataFrame()}

    df = polls.copy()
    df["end"] = df["end_date"].map(to_date)
    df["start"] = df["start_date"].map(to_date)
    df["end"] = df["end"].where(df["end"].notna(), df["start"])
    df = df[df["end"].notna()]
    df = df[df["end"] <= as_of]
    max_age = cfg.get("max_age_days", 90)
    df["age"] = df["end"].map(lambda d: (as_of - d).days)
    df = df[df["age"] <= max_age]
    df = df[pd.to_numeric(df[value_col], errors="coerce").notna()]
    if len(df) == 0:
        return {"mean": np.nan, "n_eff": 0.0, "n_polls": 0, "weights": pd.DataFrame()}

    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    n = pd.to_numeric(df.get("sample_size"), errors="coerce").fillna(cfg.get("reference_sample_size", 600))
    n = n.clip(lower=50)
    ref_n = cfg.get("reference_sample_size", 600)
    k = cfg.get("sample_size_exponent", 0.5)
    w_n = (n / ref_n) ** k

    hl = cfg.get("half_life_days", 14)
    w_t = 0.5 ** (df["age"] / hl)

    # pollster rating
    grade_lookup = {}
    if ratings is not None and len(ratings):
        for _, r in ratings.iterrows():
            grade_lookup[str(r["pollster"]).strip().lower()] = r.get("grade_or_score")
    mult_cfg = cfg.get("rating_multiplier", {"unrated": 0.65})

    def rating_mult(p):
        key = str(p).strip().lower()
        g = grade_lookup.get(key)
        if g is None:
            # fuzzy: first word match
            for kk, gg in grade_lookup.items():
                if kk and (kk in key or key in kk):
                    g = gg
                    break
        return _grade_multiplier(g, mult_cfg)
    w_r = df["pollster"].map(rating_mult) if "rating_multiplier" in cfg else pd.Series(1.0, index=df.index)

    # partisan sponsorship
    sp = df.get("sponsor_party", pd.Series("none", index=df.index)).fillna("none").astype(str).str.upper().str.strip()
    is_partisan = sp.isin(["D", "R"])
    w_p = np.where(is_partisan, cfg.get("partisan_weight_multiplier", 0.5), 1.0)
    bias = cfg.get("partisan_bias_correction_pts", 0.0)
    adj = np.where(sp == "D", -bias, np.where(sp == "R", bias, 0.0))

    # internal flag (district polls)
    if internal_col and internal_col in df.columns:
        is_int = df[internal_col].astype(str).str.lower().isin(["true", "1", "yes"])
        w_p = np.where(is_int, w_p * (internal_mult if internal_mult is not None else 1.0), w_p)
        b2 = internal_bias or 0.0
        adj = adj + np.where(is_int & (sp == "D"), -b2, np.where(is_int & (sp == "R"), b2, 0.0))

    # population adjustment
    pop_adj_cfg = cfg.get("population_adjustment_pts", {})
    pop = df.get("population", pd.Series("LV", index=df.index)).fillna("LV").astype(str).str.upper().str.strip()
    adj = adj + pop.map(lambda p: pop_adj_cfg.get(p, 0.0)).values

    df["adj_value"] = df[value_col] + adj
    df["weight"] = (w_n * w_t * w_r * w_p).astype(float)

    # same-pollster decay: rank by recency within pollster
    decay = cfg.get("same_pollster_decay", 1.0)
    df = df.sort_values("end", ascending=False)
    df["rank_in_pollster"] = df.groupby(df["pollster"].astype(str).str.lower()).cumcount()
    df["weight"] = df["weight"] * (decay ** df["rank_in_pollster"])

    wsum = df["weight"].sum()
    mean = float((df["adj_value"] * df["weight"]).sum() / wsum) if wsum > 0 else np.nan
    # effective sample size: weight-scaled sample sizes
    n_eff = float((n.loc[df.index] * (df["weight"] / df["weight"].max())).sum()) if wsum > 0 else 0.0
    df["weight_share"] = df["weight"] / wsum if wsum > 0 else 0.0
    return {"mean": mean, "n_eff": n_eff, "n_polls": int(len(df)), "weights": df}
