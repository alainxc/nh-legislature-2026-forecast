"""Run the 2026 forecast: data -> model -> simulation -> output/forecast.json.

Usage:  .venv/bin/python -m pipeline.run_forecast [--as-of YYYY-MM-DD] [--sims N]
"""
from __future__ import annotations

import argparse
from datetime import date, datetime

import numpy as np
import pandas as pd

from .common import (OUTPUT, dump_json, load_baseline, load_candidates_2026, load_config, load_districts, load_results,
                     rating_from_prob, read_csv)
from .model import (build_house_districts, build_senate_seats, compute_leans, estimate_candidate_sd, estimate_environment,
                    legislative_environment)
from .simulate import draw_shocks, house_summary, senate_summary, simulate_house, simulate_senate


def load_inputs(cfg: dict):
    districts = load_districts()
    baseline, statewide = load_baseline()
    results, cand_hist = load_results()
    cands = load_candidates_2026()
    holders = read_csv("current_holders.csv")
    regions_df = read_csv("district_regions.csv")
    regions = {(r["chamber"], r["key"]): r["region"] for _, r in regions_df.iterrows()}
    polls = read_csv("polls_statewide.csv")
    pratings = read_csv("pollster_ratings.csv")
    return dict(districts=districts, baseline=baseline, statewide=statewide, results=results, cand_hist=cand_hist,
                cands=cands, holders=holders, regions=regions, polls=polls, pratings=pratings)


def swing_curve(seats_s, dists_h, cfg, rng_seed, weeks_left, grid, n=3000, chambers=("senate", "house")):
    """For each fixed statewide generic margin on the grid: chamber control odds and expected seats,
    with regional and district noise still drawn. Powers the 'what if the polls are off' slider."""
    out = []
    for g in grid:
        rng = np.random.default_rng(rng_seed + int(round(g * 10)) % 1000)
        shocks = draw_shocks(cfg["simulation"], n, weeks_left, rng, fixed_statewide=0.0)
        rec = {"env": float(g)}
        if "senate" in chambers and seats_s is not None:
            s2 = seats_s.copy(); s2["mu"] = s2["mu"] + (g - cfg["_env_margin"])
            sim = simulate_senate(s2, shocks, rng); summ = senate_summary(s2, sim, cfg["election"]["senate_majority"])
            rec["senate"] = {k: summ[k] for k in ("p_dem_control", "p_rep_control", "p_tie", "dem_seats_mean", "dem_seats_p05", "dem_seats_p95")}
        if "house" in chambers and dists_h is not None:
            d2 = dists_h.copy(); d2["mu"] = d2["mu"] + (g - cfg["_env_margin"])
            sim = simulate_house(d2, shocks, rng, cfg["house"]); summ = house_summary(d2, sim, cfg["election"]["house_majority"])
            rec["house"] = {k: summ[k] for k in ("p_dem_control", "p_rep_control", "p_tie", "dem_seats_mean", "dem_seats_p05", "dem_seats_p95")}
        out.append(rec)
    return out


def run(as_of: date, n_sims: int | None = None, cfg: dict | None = None, quiet: bool = False) -> dict:
    cfg = cfg or load_config()
    el = cfg["election"]; chambers = el.get("chambers", ["senate", "house"])
    election_day = date.fromisoformat(el["date"])
    weeks_left = max(0.0, (election_day - as_of).days / 7.0)
    D = load_inputs(cfg)
    anchor_race = cfg["environment"]["anchor_race"]; anchor_margin = D["statewide"][anchor_race]

    env = estimate_environment(D["polls"], as_of, cfg, D["pratings"], anchor_margin, is_midterm=True,
                               presidents_party=cfg["environment"]["prior"]["presidents_party"])
    if not quiet:
        print(f"[env] anchor {anchor_margin:+.2f}  prior {env['prior_margin']:+.2f}  polls {env['poll_estimate']}  => generic {env['generic_margin']:+.2f}, "
              f"legislative {env['generic_legislative_margin']:+.2f} (swing {env['swing_vs_anchor']:+.2f}), poll share {env['poll_share_of_blend']:.0%}")
    leans = compute_leans(D["baseline"], D["statewide"], cfg["baseline"]["lean_weights"])
    leg_env = {}
    for y in (2022, 2024):
        v = legislative_environment(D["results"], y)
        leg_env[y] = v if not np.isnan(v) else cfg["baseline"]["legislative_environment_fallback"].get(y)
    sim_cfg = cfg["simulation"]
    rng = np.random.default_rng(sim_cfg["seed"])
    n = int(n_sims or sim_cfg["n_sims"])
    shocks = draw_shocks(sim_cfg, n, weeks_left, rng)

    out_chambers, seat_records, district_records = {}, [], []
    seats_s = dists_h = None
    if "senate" in chambers:
        seats_s = build_senate_seats(cfg, leans, D["cands"], D["results"], D["regions"], env, D["holders"], anchor_margin, leg_env)
        sim_s = simulate_senate(seats_s, shocks, rng)
        seats_s["p_dem"] = sim_s["seat_prob"]; seats_s["margin_mean"] = sim_s["margin_mean"]
        seats_s["margin_p05"] = sim_s["margin_p05"]; seats_s["margin_p95"] = sim_s["margin_p95"]
        seats_s["rating"] = seats_s["p_dem"].map(rating_from_prob)
        seats_s["p_flip"] = np.where(seats_s["holder_party"] == "D", 1 - seats_s["p_dem"], np.where(seats_s["holder_party"] == "R", seats_s["p_dem"], np.nan))
        out_chambers["senate"] = senate_summary(seats_s, sim_s, el["senate_majority"])
        if not quiet:
            s = out_chambers["senate"]; print(f"[senate] P(D control) {s['p_dem_control']:.1%}  mean D seats {s['dem_seats_mean']:.1f} [{s['dem_seats_p05']:.0f}-{s['dem_seats_p95']:.0f}]")
        for _, r in seats_s.iterrows():
            rec = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items() if k not in ("breakdown", "lean_components")}
            rec["breakdown"] = r["breakdown"]; rec["lean_components"] = r["lean_components"]
            seat_records.append(rec)
    cand_stats = None
    if "house" in chambers:
        cand_stats = estimate_candidate_sd(D["results"], D["cand_hist"])
        hcfg = cfg["house"]
        csd = cand_stats["candidate_sd"] if not np.isnan(cand_stats["candidate_sd"]) else hcfg["candidate_sd_pts_fallback"]
        csd = (1 - hcfg["candidate_sd_shrink"]) * csd + hcfg["candidate_sd_shrink"] * hcfg["candidate_sd_pts_fallback"]
        dists_h = build_house_districts(cfg, leans, D["cands"], D["results"], D["regions"], env, D["holders"], anchor_margin, leg_env, D["districts"], csd)
        sim_h = simulate_house(dists_h, shocks, rng, hcfg)
        out_chambers["house"] = house_summary(dists_h, sim_h, el["house_majority"])
        if not quiet:
            h = out_chambers["house"]; print(f"[house] P(D control) {h['p_dem_control']:.1%}  mean D seats {h['dem_seats_mean']:.1f} [{h['dem_seats_p05']:.0f}-{h['dem_seats_p95']:.0f}]  candidate SD {csd:.2f}")
        for j, (_, r) in enumerate(dists_h.iterrows()):
            rec = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items() if k not in ("breakdown", "lean_components", "candidates")}
            rec["breakdown"] = r["breakdown"]; rec["lean_components"] = r["lean_components"]
            rec["candidates"] = [dict(c, p_win=p) for c, p in zip(r["candidates"], sim_h["cand_probs"][j])]
            rec["d_seats_mean"] = float(sim_h["d_seats_mean"][j]); rec["r_seats_mean"] = float(sim_h["r_seats"][:, j].mean())
            rec["margin_mean"] = float(sim_h["margin_mean"][j]); rec["margin_p05"] = float(sim_h["margin_p05"][j]); rec["margin_p95"] = float(sim_h["margin_p95"][j])
            rec["seat_distribution"] = out_chambers["house"]["district_seat_distributions"][j]
            rec["p_dem"] = rec["d_seats_mean"] / r["seats"]           # expected D seat share
            rec["p_d_gain"] = float((sim_h["d_seats"][:, j] > r["held_d"]).mean()); rec["p_d_loss"] = float((sim_h["d_seats"][:, j] < r["held_d"]).mean())
            rec["rating"] = rating_from_prob(rec["p_dem"])
            district_records.append(rec)
        out_chambers["house"].pop("district_seat_distributions")

    # swing curve for the slider
    cfg["_env_margin"] = env["generic_legislative_margin"]
    grid = [round(x, 1) for x in np.arange(-12, 20.1, 0.5)]
    curve = swing_curve(seats_s, dists_h, cfg, sim_cfg["seed"] + 7, weeks_left, grid, chambers=tuple(chambers))
    cfg.pop("_env_margin")

    env_dist = env["generic_legislative_margin"] + shocks["statewide"]
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"), "as_of": as_of.isoformat(), "election_date": el["date"],
        "days_to_election": (election_day - as_of).days, "n_sims": n, "chambers_modelled": list(chambers),
        "environment": {k: v for k, v in env.items() if k != "source_polls"},
        "environment_distribution": {"mean": float(env_dist.mean()), "p05": float(np.percentile(env_dist, 5)), "p95": float(np.percentile(env_dist, 95)),
                                      "sd": float(env_dist.std()), "hist": np.histogram(env_dist, bins=np.arange(-20, 20.5, 1.0))[0].tolist(),
                                      "hist_bins": np.arange(-20, 20.5, 1.0).tolist()},
        "statewide_margins_used": D["statewide"], "legislative_environment_by_year": leg_env,
        "house_candidate_stats": cand_stats,
        "chambers": out_chambers, "seats": seat_records, "house_districts": district_records, "swing_curve": curve, "config": cfg,
    }
    dump_json(out, OUTPUT / "forecast.json")
    if seats_s is not None:
        seats_s.drop(columns=["breakdown", "lean_components"]).to_csv(OUTPUT / "senate_seats.csv", index=False)
    if dists_h is not None:
        flat = dists_h.drop(columns=["breakdown", "lean_components", "candidates"]).copy()
        flat["d_seats_mean"] = [r["d_seats_mean"] for r in district_records]
        flat.to_csv(OUTPUT / "house_districts.csv", index=False)
    env_polls = {k: v.drop(columns=[c for c in ("end", "start") if c in v.columns]).to_dict("records") for k, v in env["source_polls"].items()}
    dump_json(env_polls, OUTPUT / "environment_polls.json")
    if not quiet:
        print(f"[out] wrote {OUTPUT / 'forecast.json'}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--sims", type=int, default=None)
    a = ap.parse_args()
    run(date.fromisoformat(a.as_of), a.sims)


if __name__ == "__main__":
    main()
