"""Monte Carlo with correlated statewide, regional and district error, shared across chambers.

Senate seats are simulated at the margin level (as in the Pennsylvania model). House districts
are simulated at the candidate level: every candidate's share = party mean share (from the
district margin) + an incumbency offset + a candidate-specific deviation, and the top k by
share win the district's k seats, so seat splits and ticket splitting emerge naturally.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def draw_shocks(cfg_sim: dict, n: int, weeks_left: float, rng, fixed_statewide: float | None = None) -> dict:
    regions = list(cfg_sim["regions"])
    sw_sd = float(np.sqrt(cfg_sim["statewide_sd_pts"] ** 2 + (cfg_sim.get("statewide_sd_per_week_remaining", 0.0) * weeks_left) ** 2))

    def t_scaled(df_, sd, size):
        scale = sd * np.sqrt((df_ - 2) / df_) if df_ > 2 else sd
        return rng.standard_t(df_, size=size) * scale
    sw = np.full(n, fixed_statewide, dtype=float) if fixed_statewide is not None else t_scaled(cfg_sim.get("statewide_t_df", 5), sw_sd, n)
    rg = t_scaled(cfg_sim.get("regional_t_df", 8), cfg_sim["regional_sd_pts"], (n, len(regions)))
    return {"statewide": sw, "regional": rg, "regions": regions, "statewide_sd_used": sw_sd, "n": n}


def simulate_senate(seats: pd.DataFrame, shocks: dict, rng) -> dict:
    n = shocks["n"]; reg_idx = {r: i for i, r in enumerate(shocks["regions"])}
    mu = seats["mu"].to_numpy(dtype=float); sd_d = seats["sd_district"].to_numpy(dtype=float)
    reg = seats["region"].map(lambda r: reg_idx.get(r, 0)).to_numpy()
    margins = mu[None, :] + shocks["statewide"][:, None] + shocks["regional"][:, reg] + rng.standard_normal((n, len(seats))) * sd_d
    dem_win = margins > 0
    fixed = seats["fixed_prob"].to_numpy(dtype=float); has_fixed = ~np.isnan(fixed)
    if has_fixed.any():
        dem_win[:, has_fixed] = rng.random((n, has_fixed.sum())) < fixed[has_fixed]
    return {"seat_prob": dem_win.mean(axis=0), "margin_mean": margins.mean(axis=0),
            "margin_p05": np.percentile(margins, 5, axis=0), "margin_p95": np.percentile(margins, 95, axis=0),
            "dem_win": dem_win, "margins": margins}


def simulate_house(districts: pd.DataFrame, shocks: dict, rng, cfg_house: dict) -> dict:
    """Returns per-district D/R/I seat arrays (n x m) and per-candidate win probabilities."""
    n = shocks["n"]; reg_idx = {r: i for i, r in enumerate(shocks["regions"])}
    m = len(districts)
    d_seats = np.zeros((n, m), dtype=np.int16); r_seats = np.zeros((n, m), dtype=np.int16); i_seats = np.zeros((n, m), dtype=np.int16)
    margin_sim = np.zeros((n, m), dtype=np.float32)
    cand_probs = []
    for j, (_, d) in enumerate(districts.iterrows()):
        k = int(d["seats"]); cands = d["candidates"]
        if d["fixed_d"] is not None and not (isinstance(d["fixed_d"], float) and np.isnan(d["fixed_d"])):
            d_seats[:, j] = int(d["fixed_d"]); r_seats[:, j] = int(d["fixed_r"]); i_seats[:, j] = int(d["fixed_i"])
            margin_sim[:, j] = d["mu"]
            cand_probs.append([1.0] * len(cands))
            continue
        shock = shocks["statewide"] + shocks["regional"][:, reg_idx.get(d["region"], 0)] + rng.standard_normal(n) * float(d["sd_district"])
        margin = float(d["mu"]) + shock                      # (n,)  district party margin
        margin_sim[:, j] = margin
        share_d = 50 + margin / 2; share_r = 50 - margin / 2
        csd = float(d["candidate_sd"])
        parties = np.array([c["party"] for c in cands]); offs = np.array([c["offset_pts"] for c in cands], dtype=float)
        base = np.where(parties == "D", share_d[:, None], np.where(parties == "R", share_r[:, None], np.minimum(share_d, share_r)[:, None]))
        shares = base + offs[None, :] + rng.standard_normal((n, len(cands))) * csd
        # top-k seats
        if len(cands) > k:
            idx = np.argpartition(-shares, k - 1, axis=1)[:, :k]
        else:
            idx = np.tile(np.arange(len(cands)), (n, 1))
        win = np.zeros_like(shares, dtype=bool)
        np.put_along_axis(win, idx, True, axis=1)
        d_seats[:, j] = (win & (parties == "D")[None, :]).sum(axis=1)
        r_seats[:, j] = (win & (parties == "R")[None, :]).sum(axis=1)
        i_seats[:, j] = (win & (parties == "I")[None, :]).sum(axis=1)
        cand_probs.append(win.mean(axis=0).tolist())
    return {"d_seats": d_seats, "r_seats": r_seats, "i_seats": i_seats, "margins": margin_sim, "cand_probs": cand_probs,
            "d_seats_mean": d_seats.mean(axis=0), "margin_mean": margin_sim.mean(axis=0),
            "margin_p05": np.percentile(margin_sim, 5, axis=0), "margin_p95": np.percentile(margin_sim, 95, axis=0)}


def _control(dem_seats, rep_seats, total, majority):
    counts = np.bincount(dem_seats.astype(int), minlength=total + 1)
    dist = {int(k): int(v) for k, v in enumerate(counts) if v > 0}
    p_dem = float((dem_seats >= majority).mean()); p_rep = float((rep_seats >= majority).mean())
    return {"total_seats": int(total), "majority": int(majority), "p_dem_control": p_dem, "p_rep_control": p_rep,
            "p_tie": float(1 - p_dem - p_rep), "dem_seats_mean": float(dem_seats.mean()), "dem_seats_median": float(np.median(dem_seats)),
            "dem_seats_p05": float(np.percentile(dem_seats, 5)), "dem_seats_p95": float(np.percentile(dem_seats, 95)),
            "rep_seats_mean": float(rep_seats.mean()), "distribution": dist}


def senate_summary(seats: pd.DataFrame, sim: dict, majority: int) -> dict:
    wins = sim["dem_win"]
    cp = seats["challenger_party"].fillna("D").to_numpy()
    d_side_is_dem = cp == "D"; r_side_is_rep = cp != "I-vs-D"
    dem_seats = (wins & d_side_is_dem[None, :]).sum(axis=1); rep_seats = ((~wins) & r_side_is_rep[None, :]).sum(axis=1)
    out = _control(dem_seats, rep_seats, len(seats), majority)
    out["chamber"] = "senate"; out["ind_seats_mean"] = float((len(seats) - dem_seats - rep_seats).mean())
    margins = sim["margins"]; order = np.argsort(-margins, axis=1)
    tp_idx = order[:, majority - 1]; tp_counts = np.bincount(tp_idx, minlength=len(seats))
    keys = seats["seat"].to_numpy()
    out["tipping_point"] = dict(sorted({str(keys[i]): float(tp_counts[i] / len(dem_seats)) for i in range(len(keys)) if tp_counts[i] > 0}.items(), key=lambda kv: -kv[1]))
    return out


def house_summary(districts: pd.DataFrame, sim: dict, majority: int) -> dict:
    dem = sim["d_seats"].sum(axis=1); rep = sim["r_seats"].sum(axis=1); ind = sim["i_seats"].sum(axis=1)
    total = int(districts["seats"].sum())
    out = _control(dem, rep, total, majority)
    out["chamber"] = "house"; out["ind_seats_mean"] = float(ind.mean())
    out["p_no_majority_due_to_independents"] = float(((dem < majority) & (rep < majority) & (ind > 0)).mean())
    # per-district seat distributions
    dists = []
    for j in range(len(districts)):
        k = int(districts.iloc[j]["seats"])
        counts = np.bincount(sim["d_seats"][:, j], minlength=k + 1)[: k + 1]
        dists.append({int(i): float(c / len(dem)) for i, c in enumerate(counts)})
    out["district_seat_distributions"] = dists
    return out
