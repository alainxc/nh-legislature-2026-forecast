"""Backtest the model on 2022 and 2024 with only pre-election data, for both chambers.

Inputs rebuilt as they stood three days before each election: district leans from statewide
races held BEFORE the cycle (2020 president for 2022, the new map's first cycle; 2020 president,
2022 governor and 2022 US Senate for 2024), the ballot (names, parties, incumbency) from the
results file, the statewide environment from polls_historical.csv (NH polls only: no archived
national generic-ballot list with sources exists for those cycles), and the 2022 legislative
result as an extra lean for 2024. Scored against the actual results:
  Senate: seats called, Brier, log loss, margin error, 90% coverage, seat total.
  House:  per-seat Brier on "Democrats win at least j seats" in each district, modal seat count
          correct, seat total, and the statewide miss.
Usage: .venv/bin/python -m pipeline.backtest
"""
from __future__ import annotations

import copy
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .common import OUTPUT, dump_json, load_baseline, load_config, load_districts, load_results, read_csv
from .model import (build_house_districts, build_senate_seats, compute_leans, estimate_candidate_sd, estimate_environment,
                    legislative_environment)
from .simulate import draw_shocks, house_summary, senate_summary, simulate_house, simulate_senate

ELECTION_DAY = {2022: date(2022, 11, 8), 2024: date(2024, 11, 5)}


def ballot_from_results(cands: pd.DataFrame, year: int) -> pd.DataFrame:
    """Candidates as they stood on the ballot, in the candidates_2026 shape."""
    c = cands[cands["year"] == year].copy()
    c["party"] = c["party"].map(lambda p: p if p in ("D", "R") else "O")
    c["incumbent"] = c["incumbent_pre"]
    c["name"] = c["candidate"]
    c["note"] = ""; c["other_label"] = np.where(c["party"] == "O", "Independent", "")
    c["also_dem"] = False; c["also_rep"] = False
    return c[["chamber", "key", "party", "name", "incumbent", "note", "other_label", "also_dem", "also_rep"]]


def run_cycle(cycle: int, cfg: dict, n_sims: int = 20000) -> dict:
    bt = cfg["backtest"]; cyc = str(cycle) if str(cycle) in bt["lean_weights"] else cycle
    eday = ELECTION_DAY[cycle]; as_of = eday - timedelta(days=bt["freeze_days_before_election"])
    weeks_left = bt["freeze_days_before_election"] / 7.0
    cfg_c = copy.deepcopy(cfg)
    anchor_race = bt["anchor_race"][cyc]; cfg_c["environment"]["anchor_race"] = anchor_race
    districts = load_districts(); baseline, statewide = load_baseline(); results, cand_hist = load_results()
    anchor = statewide[anchor_race]
    polls_hist = read_csv("polls_historical.csv"); pratings = read_csv("pollster_ratings.csv")
    polls = polls_hist[polls_hist["cycle"] == cycle].copy() if polls_hist is not None else None
    regions_df = read_csv("district_regions.csv"); regions = {(r["chamber"], r["key"]): r["region"] for _, r in regions_df.iterrows()}
    env = estimate_environment(polls, as_of, cfg_c, pratings, anchor, is_midterm=(cycle % 4 == 2), presidents_party=bt["presidents_party"][cyc],
                               source_weights=bt["source_weights"][cyc], governor_personal_vote=bt["governor_personal_vote_pts"][cyc],
                               cd_adjust=bt["cd_incumbent_adjust_pts"][cyc])
    leans = compute_leans(baseline, statewide, bt["lean_weights"][cyc])
    ballot = ballot_from_results(cand_hist, cycle)
    prior_results = results[results["year"] < cycle] if cycle > 2022 else None
    leg_env = {y: legislative_environment(results, y) for y in (2022, 2024) if y < cycle}
    last_year = cycle - 2
    # "holders" = incumbents' parties (seat level) for flip accounting
    inc = ballot[ballot["incumbent"]]
    hold_rows = []
    for key, d in districts.set_index("key").iterrows():
        g = inc[inc["key"] == key]
        hold_rows.append({"key": key, "d_held": int((g["party"] == "D").sum()), "r_held": int((g["party"] == "R").sum()), "i_held": 0, "vacant": 0})
    holders = pd.DataFrame(hold_rows)
    rng = np.random.default_rng(cfg["simulation"]["seed"] + cycle)
    shocks = draw_shocks(cfg_c["simulation"], n_sims, weeks_left, rng)
    actual = results[results["year"] == cycle].set_index(["chamber", "key"])
    out = {"cycle": cycle, "as_of": as_of.isoformat(), "environment": {k: v for k, v in env.items() if k != "source_polls"},
           "inputs_used": ["district leans from statewide races before the cycle (exact by town)", "the ballot: names, parties and incumbency from the results and Wikipedia incumbent tables",
                           "NH statewide polls up to the freeze date (governor, US Senate/president, NH-01/NH-02, NH congressional generic)"] + (["2022 legislative results as an extra lean"] if cycle == 2024 else []),
           "inputs_not_available": ["national generic ballot (no archived poll list with sources)", "district polls", "outside ratings", "campaign finance"]}
    # actual legislative environment (lean- and incumbency-adjusted party margin over contested districts)
    for ch in ("house", "senate"):
        act = actual.loc[ch]
        v = legislative_environment(results, cycle, ch)
        out[f"actual_legislative_margin_{ch}"] = v
    out["actual_legislative_margin"] = legislative_environment(results, cycle)
    out["environment_error_pts"] = float(env["generic_legislative_margin"] - out["actual_legislative_margin"])

    # ---------------- Senate ----------------
    seats = build_senate_seats(cfg_c, leans, ballot, prior_results, regions, env, holders, anchor, leg_env, last_year=last_year)
    sim = simulate_senate(seats, shocks, rng)
    seats["p_dem"] = sim["seat_prob"]; seats["margin_mean"] = sim["margin_mean"]
    act_s = actual.loc["senate"]
    seats["actual_margin"] = [act_s.loc[k, "party_margin"] for k in seats["key"]]
    seats["actual_dem_win"] = [act_s.loc[k, "d_seats"] > 0 for k in seats["key"]]
    con = seats[~seats["uncontested"] & seats["actual_margin"].notna()].copy()
    p = con["p_dem"].clip(0.005, 0.995); y = con["actual_dem_win"].astype(float)
    err = con["actual_margin"] - con["margin_mean"]
    mask = (~seats["uncontested"] & seats["actual_margin"].notna()).to_numpy()
    in90 = ((con["actual_margin"] >= sim["margin_p05"][mask]) & (con["actual_margin"] <= sim["margin_p95"][mask])).mean()
    summ = senate_summary(seats, sim, cfg["election"]["senate_majority"])
    out["senate"] = {
        "n_seats": int(len(seats)), "n_contested": int(len(con)), "seats_called_correctly": int(((con["p_dem"] > 0.5) == con["actual_dem_win"]).sum()),
        "accuracy": float(((con["p_dem"] > 0.5) == con["actual_dem_win"]).mean()), "brier": float(((p - y) ** 2).mean()),
        "log_loss": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()), "margin_mae": float(err.abs().mean()), "margin_bias": float(err.mean()),
        "margin_rmse": float(np.sqrt((err ** 2).mean())), "coverage_90": float(in90),
        "pred_mean": summ["dem_seats_mean"], "pred_p05": summ["dem_seats_p05"], "pred_p95": summ["dem_seats_p95"], "p_dem_control": summ["p_dem_control"],
        "actual_dem_seats": int(seats["actual_dem_win"].sum()),
        "misses": con[(con["p_dem"] > 0.5) != con["actual_dem_win"]][["seat", "p_dem", "margin_mean", "actual_margin", "dem_cand", "rep_cand"]].to_dict("records"),
        "seats": seats[["seat", "p_dem", "margin_mean", "actual_margin", "actual_dem_win", "uncontested", "incumbent_party", "dem_cand", "rep_cand"]].to_dict("records"),
    }
    # ---------------- House ----------------
    cstats = estimate_candidate_sd(results, cand_hist, years=tuple(y for y in (2022, 2024) if y < cycle) or (2022, 2024))
    hcfg = cfg["house"]
    csd = cstats["candidate_sd"] if not np.isnan(cstats["candidate_sd"]) else hcfg["candidate_sd_pts_fallback"]
    csd = (1 - hcfg["candidate_sd_shrink"]) * csd + hcfg["candidate_sd_shrink"] * hcfg["candidate_sd_pts_fallback"]
    dists = build_house_districts(cfg_c, leans, ballot, prior_results, regions, env, holders, anchor, leg_env, districts, csd, last_year=last_year)
    simh = simulate_house(dists, shocks, rng, hcfg)
    hs = house_summary(dists, simh, cfg["election"]["house_majority"])
    act_h = actual.loc["house"]
    rows, briers, called, nseat_events, abs_err, modal_ok, n_contested = [], [], 0, 0, 0.0, 0, 0
    for j, (_, d) in enumerate(dists.iterrows()):
        k = int(d["seats"]); a = int(act_h.loc[d["key"], "d_seats"]); dist = hs["district_seat_distributions"][j]
        exp_d = float(simh["d_seats_mean"][j]); mode = max(dist, key=dist.get)
        rec = {"key": d["key"], "seats": k, "contested": bool(d["contested"]), "expected_d_seats": exp_d, "modal_d_seats": int(mode), "actual_d_seats": a,
               "p_at_least": {str(jj): float(sum(v for kk, v in dist.items() if kk >= jj)) for jj in range(1, k + 1)}, "margin_mean": float(simh["margin_mean"][j]),
               "actual_margin": None if pd.isna(act_h.loc[d["key"], "party_margin"]) else float(act_h.loc[d["key"], "party_margin"])}
        rows.append(rec)
        if d["contested"]:
            n_contested += 1; abs_err += abs(exp_d - a); modal_ok += int(mode == a)
            for jj in range(1, k + 1):
                pj = min(max(rec["p_at_least"][str(jj)], 0.005), 0.995); yj = float(a >= jj)
                briers.append((pj - yj) ** 2); called += int((pj > 0.5) == (yj > 0.5)); nseat_events += 1
    cmask = dists["contested"].to_numpy()
    out["house"] = {
        "n_districts": int(len(dists)), "n_contested_districts": n_contested, "n_contested_seats": nseat_events,
        "seats_called_correctly": called, "accuracy": called / max(nseat_events, 1), "brier": float(np.mean(briers)) if briers else None,
        "modal_seat_count_correct": modal_ok, "modal_accuracy": modal_ok / max(n_contested, 1), "seat_mae_per_contested_district": abs_err / max(n_contested, 1),
        "pred_mean": hs["dem_seats_mean"], "pred_p05": hs["dem_seats_p05"], "pred_p95": hs["dem_seats_p95"], "p_dem_control": hs["p_dem_control"],
        "actual_dem_seats": int(act_h["d_seats"].sum()), "candidate_sd_used": csd, "candidate_stats": cstats,
        "margin_mae_contested": float(np.nanmean([abs(r["actual_margin"] - r["margin_mean"]) for r in rows if r["contested"] and r["actual_margin"] is not None])),
        "margin_bias_contested": float(np.nanmean([(r["actual_margin"] - r["margin_mean"]) for r in rows if r["contested"] and r["actual_margin"] is not None])),
        "biggest_misses": sorted([r for r in rows if r["contested"]], key=lambda r: -abs(r["expected_d_seats"] - r["actual_d_seats"]))[:15],
        "districts": rows,
    }
    return out


def main():
    cfg = load_config()
    out = {}
    for cycle in cfg["backtest"]["cycles"]:
        r = run_cycle(cycle, cfg)
        out[str(cycle)] = r
        e = r["environment"]; s = r["senate"]; h = r["house"]
        print(f"[backtest {cycle}] env generic {e['generic_margin']:+.2f} legislative {e['generic_legislative_margin']:+.2f} vs actual {r['actual_legislative_margin']:+.2f} (house {r['actual_legislative_margin_house']:+.2f}, senate {r['actual_legislative_margin_senate']:+.2f}); poll share {e['poll_share_of_blend']:.0%}")
        print(f"   senate: called {s['seats_called_correctly']}/{s['n_contested']} Brier {s['brier']:.3f} MAE {s['margin_mae']:.1f} bias {s['margin_bias']:+.1f} cov90 {s['coverage_90']:.0%} | D seats pred {s['pred_mean']:.1f} [{s['pred_p05']:.0f}-{s['pred_p95']:.0f}] actual {s['actual_dem_seats']}")
        print(f"   house: seat-events called {h['seats_called_correctly']}/{h['n_contested_seats']} ({h['accuracy']:.1%}) Brier {h['brier']:.3f} | modal seat count right {h['modal_seat_count_correct']}/{h['n_contested_districts']} | "
              f"D seats pred {h['pred_mean']:.1f} [{h['pred_p05']:.0f}-{h['pred_p95']:.0f}] actual {h['actual_dem_seats']} | margin MAE {h['margin_mae_contested']:.1f} bias {h['margin_bias_contested']:+.1f}")
    dump_json(out, OUTPUT / "backtest.json")


if __name__ == "__main__":
    main()
