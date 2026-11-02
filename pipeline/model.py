"""District-level model for New Hampshire: statewide environment, district leans, the
single-member Senate seat model and the multi-member House district model.

Every function returns both numbers and a breakdown dict so each district page can show
exactly how each input moved it.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .common import rating_from_prob, two_party_margin
from .polls import weighted_poll_average


# ----------------------------------------------------------------------
# Statewide environment
# ----------------------------------------------------------------------
def estimate_environment(polls: pd.DataFrame | None, as_of: date, cfg: dict, ratings: pd.DataFrame | None,
                         anchor_margin: float, is_midterm: bool, presidents_party: str,
                         source_weights: dict | None = None, governor_personal_vote: float | None = None,
                         cd_adjust: dict | None = None) -> dict:
    """Return the statewide generic-legislative Dem margin forecast and the swing vs the anchor.

    Poll types: nh_legislative_generic (used directly), nh_governor (personal-vote corrected),
    nh_congressional_generic, nh_cd1/nh_cd2 (combined as nh_congressional_districts),
    national_generic_ballot, and for backtests nh_us_senate (as a statewide federal race) and
    nh_president (a direct read of the anchor-type quantity).
    """
    env = cfg["environment"]
    pcfg = env["polls"]
    weights = dict(source_weights or env["source_weights"])
    gpv = env["governor_personal_vote_pts"] if governor_personal_vote is None else governor_personal_vote
    cd_adj = cd_adjust or env.get("cd_incumbent_adjust_pts", {})
    sources = {}
    if polls is not None and len(polls):
        p = polls.copy()
        p.loc[p["poll_type"].isin(["nh_cd1", "nh_cd2"]), "poll_group"] = "nh_congressional_districts"
        p["poll_group"] = p["poll_group"].fillna(p["poll_type"])
        for ptype, sub in p.groupby("poll_group"):
            if ptype not in weights:
                continue
            if ptype == "nh_congressional_districts":
                parts, tables, n_polls, n_eff = [], [], 0, 0.0
                for cd, s2 in sub.groupby("poll_type"):
                    avg = weighted_poll_average(s2, as_of, pcfg, ratings)
                    if np.isnan(avg["mean"]):
                        continue
                    parts.append(avg["mean"] + float(cd_adj.get(cd, 0.0)))
                    n_polls += avg["n_polls"]; n_eff += avg["n_eff"]
                    w = avg["weights"].copy(); w["poll_type"] = cd; tables.append(w)
                if not parts:
                    continue
                raw = float(np.mean(parts))
                est = anchor_margin + env["cd_pass_through"] * (raw - anchor_margin)
                how = (f"NH-01/NH-02 head-to-heads, incumbent bonus removed ({', '.join(f'{k} {v:+.0f}' for k, v in cd_adj.items())}), "
                       f"averaged {raw:+.1f}; {env['cd_pass_through']:.0%} pass-through from the anchor")
                sources[ptype] = {"raw_average": raw, "implied_generic_margin": est, "n_polls": n_polls, "n_eff": n_eff / 2,
                                  "weight": weights[ptype], "how": how, "polls": pd.concat(tables) if tables else pd.DataFrame()}
                continue
            avg = weighted_poll_average(sub, as_of, pcfg, ratings)
            if np.isnan(avg["mean"]):
                continue
            raw = avg["mean"]
            if ptype == "nh_legislative_generic":
                est, how = raw, "used directly (asks which party should control the legislature)"
            elif ptype == "nh_president":
                est, how = raw, "presidential head-to-head read as the statewide two-party environment"
            elif ptype == "nh_governor":
                est = anchor_margin + env["governor_pass_through"] * ((raw - gpv) - anchor_margin)
                how = (f"governor margin {raw:+.1f} minus the governor's personal vote ({gpv:+.0f}) = {raw - gpv:+.1f}; "
                       f"{env['governor_pass_through']:.0%} of the way from the anchor")
            elif ptype in ("nh_congressional_generic", "nh_us_senate"):
                est = anchor_margin + env["nh_congressional_pass_through"] * (raw - anchor_margin)
                how = f"statewide federal preference {raw:+.1f}; {env['nh_congressional_pass_through']:.0%} pass-through from the anchor"
            elif ptype == "national_generic_ballot":
                nh = raw + env["nh_lean_vs_nation_pts"]
                est = anchor_margin + env["national_pass_through"] * (nh - anchor_margin)
                how = (f"national generic {raw:+.1f} plus NH lean vs nation {env['nh_lean_vs_nation_pts']:+.1f} = {nh:+.1f}; "
                       f"{env['national_pass_through']:.0%} pass-through from the anchor")
            else:
                continue
            sources[ptype] = {"raw_average": raw, "implied_generic_margin": est, "n_polls": avg["n_polls"], "n_eff": avg["n_eff"],
                              "weight": weights[ptype], "how": how, "polls": avg["weights"]}
    if sources:
        wsum = sum(s["weight"] for s in sources.values())
        poll_est = sum(s["weight"] * s["implied_generic_margin"] for s in sources.values()) / wsum
        n_eff_total = sum(s["n_eff"] * s["weight"] for s in sources.values()) / wsum
    else:
        poll_est, n_eff_total = np.nan, 0.0
    prior_cfg = env["prior"]
    sign = 1.0 if presidents_party.upper() == "R" else -1.0
    prior_margin = anchor_margin + (sign * prior_cfg["midterm_swing_pts_toward_out_party"] if is_midterm else 0.0)
    prior_n = prior_cfg["prior_effective_n"]
    if np.isnan(poll_est):
        final, poll_share = prior_margin, 0.0
    else:
        final = (prior_n * prior_margin + n_eff_total * poll_est) / (prior_n + n_eff_total)
        poll_share = n_eff_total / (prior_n + n_eff_total)
    offset = env.get("legislative_vs_anchor_offset_pts", 0.0)
    final_leg = final + offset
    return {
        "as_of": as_of.isoformat(), "anchor_margin": anchor_margin, "prior_margin": prior_margin, "prior_effective_n": prior_n,
        "poll_estimate": None if np.isnan(poll_est) else poll_est, "poll_n_eff": n_eff_total, "poll_share_of_blend": poll_share,
        "generic_margin": final, "legislative_offset": offset, "generic_legislative_margin": final_leg,
        "swing_vs_anchor": final_leg - anchor_margin,
        "sources": {k: {kk: vv for kk, vv in v.items() if kk != "polls"} for k, v in sources.items()},
        "source_polls": {k: v["polls"] for k, v in sources.items()},
    }


# ----------------------------------------------------------------------
# Baseline lean
# ----------------------------------------------------------------------
def compute_leans(baseline: pd.DataFrame, statewide: dict, lean_weights: dict) -> pd.DataFrame:
    rows = []
    for _, r in baseline.iterrows():
        comps, wsum, acc = {}, 0.0, 0.0
        for race, w in lean_weights.items():
            col = f"{race}_margin"
            if col not in r or pd.isna(r[col]) or race not in statewide:
                continue
            lean = float(r[col]) - statewide[race]
            comps[race] = {"district_margin": float(r[col]), "statewide_margin": statewide[race], "lean": lean, "weight": w}
            acc += w * lean; wsum += w
        rows.append({"chamber": r["chamber"], "key": r["key"], "lean": acc / wsum if wsum > 0 else np.nan,
                     "lean_components": comps, "races_used": len(comps)})
    return pd.DataFrame(rows)


def legislative_environment(results: pd.DataFrame, year: int, chamber: str | None = None) -> float:
    """Vote-weighted party margin (mean votes per D candidate vs mean per R candidate) across
    contested districts in a year. This is the NH 'legislative environment'."""
    sub = results[results["year"] == year]
    if chamber:
        sub = sub[sub["chamber"] == chamber]
    sub = sub[sub["contested"] & sub["party_margin"].notna()]
    if len(sub) == 0:
        return np.nan
    w = sub["mean_d_votes"] + sub["mean_r_votes"]
    return float((sub["party_margin"] * w).sum() / w.sum())


# ----------------------------------------------------------------------
# Shared pieces
# ----------------------------------------------------------------------
def _past_result_lean(results: pd.DataFrame | None, chamber: str, key: str, yr: int, leg_env: dict, cfg: dict) -> tuple[float, dict | None]:
    """The district's last legislative party margin as a lean vs that year's legislative environment,
    with the incumbency bonus the then-incumbents enjoyed removed (per seat, averaged)."""
    bcfg, cc = cfg["baseline"], cfg["candidates"]
    if results is None or yr not in leg_env or np.isnan(leg_env.get(yr, np.nan)):
        return np.nan, None
    past = results[(results["chamber"] == chamber) & (results["key"] == key) & (results["year"] == yr)]
    if not len(past):
        return np.nan, None
    p = past.iloc[0]
    if not p["contested"] or pd.isna(p["party_margin"]) or abs(p["party_margin"]) > bcfg["legislative_result_max_margin"]:
        return np.nan, {"year": int(yr), "margin": None if pd.isna(p["party_margin"]) else float(p["party_margin"]), "used": False,
                        "reason": "uncontested or lopsided"}
    inc_pts = cc["incumbency_advantage_pts"] if chamber == "senate" else cc["house_incumbency_advantage_pts"]
    n_d, n_r = max(int(p["n_d"]), 1), max(int(p["n_r"]), 1)
    inc_adj = inc_pts * (p["inc_d_running"] / n_d - p["inc_r_running"] / n_r)
    lean = float(p["party_margin"]) - leg_env[yr] - inc_adj
    return lean, {"year": int(yr), "margin": float(p["party_margin"]), "leg_environment": leg_env[yr], "incumbency_removed": float(inc_adj),
                  "lean": lean, "used": True}


def _blend_lean(lean: float, leg_lean: float, w: float) -> tuple[float, str | None]:
    if np.isnan(lean) and np.isnan(leg_lean):
        return 0.0, "no baseline data; assumed even"
    if np.isnan(leg_lean):
        return lean, None
    if np.isnan(lean):
        return leg_lean, None
    return (1 - w) * lean + w * leg_lean, None


# ----------------------------------------------------------------------
# Senate (single-member)
# ----------------------------------------------------------------------
def build_senate_seats(cfg: dict, leans: pd.DataFrame, cands: pd.DataFrame, results: pd.DataFrame | None,
                       regions: dict, env: dict, holders: pd.DataFrame, anchor_margin: float, leg_env: dict,
                       last_year: int = 2024) -> pd.DataFrame:
    """cands: long form (key, party D/R/O, name, incumbent, note, other_label). One row per seat."""
    cc, sim, bcfg = cfg["candidates"], cfg["simulation"], cfg["baseline"]
    sd_base = float(np.sqrt(sim["statewide_sd_pts"] ** 2 + sim["regional_sd_pts"] ** 2 + sim["district_sd_pts"] ** 2))
    hold = holders.set_index("key") if holders is not None else None
    rows = []
    for key, grp in cands[(cands["chamber"] == "senate")].groupby("key", sort=False):
        grp = grp[grp["note"] == ""]
        lr = leans[(leans["chamber"] == "senate") & (leans["key"] == key)]
        lean = float(lr["lean"].iloc[0]) if len(lr) and pd.notna(lr["lean"].iloc[0]) else np.nan
        lean_components = lr["lean_components"].iloc[0] if len(lr) else {}
        breakdown = {}
        leg_lean, leg_used = _past_result_lean(results, "senate", key, last_year, leg_env, cfg)
        base_lean, note = _blend_lean(lean, leg_lean, bcfg["legislative_result_weight"])
        if note: breakdown["baseline_note"] = note
        breakdown["lean_from_statewide_races"] = None if np.isnan(lean) else lean
        breakdown["lean_from_last_legislative_result"] = leg_used
        breakdown["baseline_lean"] = base_lean
        env_margin = anchor_margin + env["swing_vs_anchor"]
        fundamentals = env_margin + base_lean
        breakdown["statewide_generic_margin"] = env_margin
        breakdown["fundamentals_before_candidates"] = fundamentals

        d = grp[grp["party"] == "D"]; r = grp[grp["party"] == "R"]; o = grp[grp["party"] == "O"]
        dem_cand = d["name"].iloc[0] if len(d) else None
        rep_cand = r["name"].iloc[0] if len(r) else None
        has_d, has_r = dem_cand is not None, rep_cand is not None
        inc_party = "D" if (len(d) and d["incumbent"].iloc[0]) else ("R" if (len(r) and r["incumbent"].iloc[0]) else None)
        inc_name = dem_cand if inc_party == "D" else rep_cand if inc_party == "R" else None
        challenger_party = "D"
        ind_cfg = cc.get("independent_challenger", {})
        if ind_cfg.get("enabled") and len(o) and (has_d != has_r):
            ind_name = o["name"].iloc[0]
            if not has_d:
                dem_cand, has_d, challenger_party = f"{ind_name} ({o['other_label'].iloc[0] or 'Independent'})", True, "I"
            else:
                rep_cand, has_r, challenger_party = f"{ind_name} ({o['other_label'].iloc[0] or 'Independent'})", True, "I-vs-D"
            breakdown["independent_challenger"] = {"name": ind_name, "replaces": "D" if challenger_party == "I" else "R",
                                                   "penalty_pts": ind_cfg.get("baseline_penalty_pts", 6.0)}
        uncontested = has_d != has_r
        if challenger_party != "D":
            uncontested = False
        open_seat = inc_party is None
        adj = {}
        if inc_party in ("D", "R"):
            adj["incumbency"] = cc["incumbency_advantage_pts"] * (1 if inc_party == "D" else -1)
            if leg_used and leg_used.get("used"):
                over = leg_used["margin"] - (leg_env[leg_used["year"]] + (lean if not np.isnan(lean) else 0.0)) - adj["incumbency"]
                adj["prior_performance"] = float(np.clip(over * cc["prior_performance_carryover"], -cc["prior_performance_cap_pts"], cc["prior_performance_cap_pts"]))
        for ov in cc.get("quality_overrides", []) or []:
            if ov.get("chamber") == "senate" and str(ov.get("key")) == key:
                adj["quality_override"] = float(ov["adjustment_pts"]); breakdown["quality_override_reason"] = ov.get("reason")
        if challenger_party == "I":
            adj["independent_penalty"] = -float(ind_cfg.get("baseline_penalty_pts", 6.0))
        elif challenger_party == "I-vs-D":
            adj["independent_penalty"] = float(ind_cfg.get("baseline_penalty_pts", 6.0))
        if not uncontested:
            if not has_d: adj["missing_dem_candidate"] = -cc["missing_candidate_penalty_pts"]
            if not has_r: adj["missing_rep_candidate"] = cc["missing_candidate_penalty_pts"]
        mu = fundamentals + sum(adj.values())
        breakdown["candidate_adjustments"] = adj
        breakdown["fundamentals_margin"] = mu
        breakdown["final_margin"] = mu
        sd_d = sim["district_sd_pts"]
        if open_seat: sd_d = float(np.sqrt(sd_d ** 2 + sim["open_seat_extra_sd_pts"] ** 2))
        if not (leg_used and leg_used.get("used")): sd_d = float(np.sqrt(sd_d ** 2 + sim["no_recent_result_extra_sd_pts"] ** 2))
        if challenger_party != "D": sd_d = float(np.sqrt(sd_d ** 2 + float(ind_cfg.get("extra_sd_pts", 3.0)) ** 2))
        fixed = np.nan
        if uncontested:
            fixed = cc["uncontested_win_prob"] if (has_d and not has_r) else 1 - cc["uncontested_win_prob"]
        hp = "other"
        if hold is not None and key in hold.index:
            h = hold.loc[key]
            hp = "D" if h["d_held"] > 0 else "R" if h["r_held"] > 0 else "other"
        rows.append({
            "seat": key, "chamber": "senate", "key": key, "seats": 1, "region": regions.get(("senate", key), "concord_merrimack"),
            "holder_party": hp, "dem_cand": dem_cand if has_d else None, "rep_cand": rep_cand if has_r else None,
            "other_cands": "; ".join(f"{n} ({l or 'Independent'})" for n, l in zip(o["name"], o["other_label"])) if len(o) and challenger_party == "D" else None,
            "incumbent_name": inc_name, "incumbent_party": inc_party, "incumbent_running": inc_party is not None,
            "open_seat": open_seat, "uncontested": uncontested, "challenger_party": challenger_party,
            "lean": lean, "lean_components": lean_components, "mu": mu, "mu_fundamentals": mu, "sd_district": sd_d,
            "sd_total_approx": float(np.sqrt(sd_base ** 2 - sim["district_sd_pts"] ** 2 + sd_d ** 2)),
            "fixed_prob": fixed, "breakdown": breakdown,
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# House (multi-member, candidate level)
# ----------------------------------------------------------------------
def estimate_candidate_sd(results: pd.DataFrame, cands: pd.DataFrame, years=(2022, 2024)) -> dict:
    """Within-district spread of same-party candidates' shares (pts of mean-D + mean-R), and the
    incumbent-minus-non-incumbent gap within party and district, from past House results."""
    devs, inc_gaps = [], []
    res = results[(results["chamber"] == "house") & results["year"].isin(years) & results["contested"]]
    cc = cands[(cands["chamber"] == "house") & cands["year"].isin(years) & cands["votes"].notna()]
    grouped = {k: g for k, g in cc.groupby(["year", "key"])}
    for _, r in res.iterrows():
        g = grouped.get((r["year"], r["key"]))
        if g is None: continue
        tot = r["mean_d_votes"] + r["mean_r_votes"]
        if tot <= 0: continue
        for p in ("D", "R"):
            gp = g[g["party"] == p]
            if len(gp) < 2: continue
            sh = 100 * gp["votes"].to_numpy() / tot
            devs.extend(sh - sh.mean())
            inc = gp["incumbent_pre"].to_numpy()
            if inc.any() and (~inc).any():
                inc_gaps.append(sh[inc].mean() - sh[~inc].mean())
    devs = np.array(devs)
    return {"candidate_sd": float(devs.std()) if len(devs) else np.nan, "n_candidates": int(len(devs)),
            "incumbent_gap_mean": float(np.mean(inc_gaps)) if inc_gaps else np.nan, "n_incumbent_pairs": len(inc_gaps)}


def build_house_districts(cfg: dict, leans: pd.DataFrame, cands: pd.DataFrame, results: pd.DataFrame | None,
                          regions: dict, env: dict, holders: pd.DataFrame | None, anchor_margin: float, leg_env: dict,
                          districts: pd.DataFrame, candidate_sd: float, last_year: int = 2024) -> pd.DataFrame:
    """One row per House district (base or floterial). Each row carries the district party margin
    expectation `mu`, the shared district SD, and a list of candidates with their mean share
    offsets; the simulation draws candidate shares and seats the top k."""
    cc, sim, bcfg, hcfg = cfg["candidates"], cfg["simulation"], cfg["baseline"], cfg["house"]
    inc_pts = cc["house_incumbency_advantage_pts"]
    hold = holders.set_index("key") if holders is not None else None
    dmeta = districts.set_index("key")
    rows = []
    for key, dm in dmeta[dmeta["chamber"] == "house"].iterrows():
        seats = int(dm["seats"])
        grp = cands[(cands["chamber"] == "house") & (cands["key"] == key) & (cands["note"] == "")]
        lr = leans[(leans["chamber"] == "house") & (leans["key"] == key)]
        lean = float(lr["lean"].iloc[0]) if len(lr) and pd.notna(lr["lean"].iloc[0]) else np.nan
        lean_components = lr["lean_components"].iloc[0] if len(lr) else {}
        breakdown = {}
        leg_lean, leg_used = _past_result_lean(results, "house", key, last_year, leg_env, cfg)
        base_lean, note = _blend_lean(lean, leg_lean, bcfg["legislative_result_weight"])
        if note: breakdown["baseline_note"] = note
        breakdown["lean_from_statewide_races"] = None if np.isnan(lean) else lean
        breakdown["lean_from_last_legislative_result"] = leg_used
        breakdown["baseline_lean"] = base_lean
        env_margin = anchor_margin + env["swing_vs_anchor"]
        mu = env_margin + base_lean
        breakdown["statewide_generic_margin"] = env_margin
        breakdown["district_party_margin"] = mu
        cand_list = []
        n_d = int((grp["party"] == "D").sum()); n_r = int((grp["party"] == "R").sum())
        for _, c in grp.iterrows():
            party = c["party"]
            if party == "O":
                party_eff = "D" if c["also_dem"] else "R" if c["also_rep"] else "I"
            else:
                party_eff = party
            offset = inc_pts if c["incumbent"] else 0.0
            cand_list.append({"name": c["name"], "party": party_eff, "ballot_party": party if party != "O" else (c["other_label"] or "Independent"),
                              "incumbent": bool(c["incumbent"]), "offset_pts": offset})
        # independents: share drawn around the weaker major party's mean minus a penalty
        for cnd in cand_list:
            if cnd["party"] == "I":
                cnd["offset_pts"] = -cc["independent_challenger"]["baseline_penalty_pts"]
        inc_d = sum(1 for c in cand_list if c["party"] == "D" and c["incumbent"]); inc_r = sum(1 for c in cand_list if c["party"] == "R" and c["incumbent"])
        contested = n_d > 0 and n_r > 0 and len(cand_list) > seats
        # fixed outcomes: everyone on the ballot wins
        fixed_d = fixed_r = fixed_i = None
        if len(cand_list) <= seats:
            fixed_d = sum(1 for c in cand_list if c["party"] == "D"); fixed_r = sum(1 for c in cand_list if c["party"] == "R")
            fixed_i = sum(1 for c in cand_list if c["party"] == "I")
        sd_d = sim["house_district_sd_pts"]
        if not (leg_used and leg_used.get("used")): sd_d = float(np.sqrt(sd_d ** 2 + sim["no_recent_result_extra_sd_pts"] ** 2))
        hd = hr = hi = hv = 0
        if hold is not None and key in hold.index:
            h = hold.loc[key]; hd, hr, hi, hv = int(h["d_held"]), int(h["r_held"]), int(h["i_held"]), int(h["vacant"])
        rows.append({
            "seat": key, "chamber": "house", "key": key, "district_id": dm["district_id"], "county": dm["county"], "floterial": bool(dm["floterial"]),
            "seats": seats, "region": regions.get(("house", key), "concord_merrimack"), "towns": dm["towns"],
            "held_d": hd, "held_r": hr, "held_i": hi, "vacant": hv,
            "n_d": n_d, "n_r": n_r, "n_other": len(cand_list) - n_d - n_r, "inc_d": inc_d, "inc_r": inc_r,
            "contested": contested, "uncontested": not contested,
            "fixed_d": fixed_d, "fixed_r": fixed_r, "fixed_i": fixed_i,
            "lean": lean, "lean_components": lean_components, "mu": mu, "sd_district": sd_d, "candidate_sd": candidate_sd,
            "candidates": cand_list, "breakdown": breakdown,
        })
    return pd.DataFrame(rows)
