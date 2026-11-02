"""Render the static site from output/forecast.json (+ backtest.json, changelog, methodology)."""
from __future__ import annotations

import json
import re
import shutil

import pandas as pd
import yaml
from jinja2 import Environment, FileSystemLoader

from .common import OUTPUT, RATING_ORDER, ROOT, SITE, read_csv

TEMPLATES = ROOT / "templates"
RACE_LABEL = {"pres_2024": "2024 President", "gov_2024": "2024 Governor", "sen_2022": "2022 U.S. Senate", "gov_2022": "2022 Governor",
              "pres_2020": "2020 President", "cong_2022": "2022 U.S. House", "cong_2024": "2024 U.S. House"}
SOURCE_LABEL = {"nh_legislative_generic": "New Hampshire legislative generic ballot (UNH)", "nh_governor": "Governor: Ayotte v. Warmington",
                "nh_congressional_generic": "New Hampshire voters' U.S. House preference", "nh_congressional_districts": "NH-01 and NH-02 head-to-head polls",
                "national_generic_ballot": "National generic congressional ballot", "nh_us_senate": "U.S. Senate (Hassan v. Bolduc)", "nh_president": "President (Harris v. Trump) in New Hampshire"}
ADJ_LABEL = {"incumbency": "Incumbency advantage", "prior_performance": "Incumbent's past over-performance (shrunk)", "quality_override": "Candidate-quality override",
             "missing_dem_candidate": "No Democratic candidate on file", "missing_rep_candidate": "No Republican candidate on file", "independent_penalty": "Independent running without a party"}


def fmt_m(m):
    if m is None or (isinstance(m, float) and m != m):
        return "—"
    return (("D+" if m > 0 else "R+") + f"{abs(m):.1f}") if abs(m) >= 0.05 else "even"


def fmt_pm(m):
    if m is None or (isinstance(m, float) and m != m):
        return "—"
    return f"{m:+.1f}"


def md_to_html(md: str) -> str:
    out, in_list, in_table = [], False, False
    for line in md.splitlines():
        l = line.rstrip()
        if l.startswith("|"):
            cells = [c.strip() for c in l.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", c) for c in cells):
                continue
            if not in_table:
                out.append("<table>"); in_table = True
                out.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells) + "</tr>"); continue
            out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>"); continue
        if in_table:
            out.append("</table>"); in_table = False
        if l.startswith("- "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(l[2:])}</li>"); continue
        if in_list:
            out.append("</ul>"); in_list = False
        if l.startswith("### "): out.append(f"<h3>{inline(l[4:])}</h3>")
        elif l.startswith("## "): out.append(f"<h2>{inline(l[3:])}</h2>")
        elif l.startswith("# "): out.append(f"<h1>{inline(l[2:])}</h1>")
        elif l.strip() == "": continue
        else: out.append(f"<p>{inline(l)}</p>")
    if in_list: out.append("</ul>")
    if in_table: out.append("</table>")
    return "\n".join(out)


def inline(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    return s


def main():
    f = json.loads((OUTPUT / "forecast.json").read_text())
    bt = json.loads((OUTPUT / "backtest.json").read_text()) if (OUTPUT / "backtest.json").exists() else {}
    env_polls = json.loads((OUTPUT / "environment_polls.json").read_text()) if (OUTPUT / "environment_polls.json").exists() else {}
    cfg = f["config"]
    regions_cfg = yaml.safe_load(open(ROOT / "config" / "regions.yaml"))
    region_label = regions_cfg["labels"]
    chambers = f["chambers_modelled"]
    tipping = f["chambers"]["senate"]["tipping_point"] if "senate" in f["chambers"] else {}
    for s in f["seats"]:
        s["label"] = "Senate District " + str(s["key"][1:])
        s["region_label"] = region_label.get(s["region"], s["region"])
        s["tipping"] = tipping.get(s["seat"], 0.0)
    for d in f["house_districts"]:
        d["label"] = d["district_id"] + (" (floterial)" if d["floterial"] else "")
        d["region_label"] = region_label.get(d["region"], d["region"])
        d["town_list"] = d["towns"].split("|")
        d["p_change"] = max(d["p_d_gain"], d["p_d_loss"])
    seats = f["seats"]; hd = f["house_districts"]
    # backtest misses for the slider presets: actual legislative margin minus the forecast
    misses = {}
    for cyc, r in bt.items():
        misses[cyc] = r["actual_legislative_margin"] - r["environment"]["generic_legislative_margin"]
    summary = {"n_sims": f["n_sims"], "chambers": f["chambers"], "chambers_modelled": chambers,
               "seats": [{k: s.get(k) for k in ("seat", "key", "chamber", "label", "region", "region_label", "holder_party", "dem_cand", "rep_cand", "incumbent_name", "open_seat", "uncontested",
                                                "challenger_party", "lean", "mu", "margin_mean", "p_dem", "p_flip", "rating", "tipping", "sd_district", "fixed_prob")} for s in seats],
               "house": [{k: d.get(k) for k in ("key", "district_id", "label", "county", "floterial", "seats", "region", "region_label", "held_d", "held_r", "held_i", "vacant", "n_d", "n_r", "n_other",
                                               "inc_d", "inc_r", "contested", "lean", "mu", "margin_mean", "d_seats_mean", "r_seats_mean", "p_dem", "p_d_gain", "p_d_loss", "p_change", "rating", "town_list")} for d in hd],
               "swing_curve": f["swing_curve"],
               "env": {"margin": f["environment"]["generic_legislative_margin"], "regional_sd": cfg["simulation"]["regional_sd_pts"],
                       "statewide_sd": f["environment_distribution"]["sd"], "backtest_misses": misses}}
    summary_json = json.dumps(summary)
    flips = sorted([s for s in seats if s.get("p_flip") is not None], key=lambda s: -s["p_flip"])
    closest = sorted([s for s in seats if not s["uncontested"]], key=lambda s: abs(s["p_dem"] - 0.5))
    house_moves = sorted([d for d in hd if d["contested"]], key=lambda d: -(abs(d["d_seats_mean"] - d["held_d"]) if d["vacant"] == 0 else abs(d["d_seats_mean"] - d["held_d"])))
    house_closest = sorted([d for d in hd if d["contested"]], key=lambda d: abs(d["p_dem"] - 0.5))
    by_rating = {"senate": {r: [s for s in seats if s["rating"] == r] for r in RATING_ORDER}, "house": {r: [d for d in hd if d["rating"] == r] for r in RATING_ORDER}}
    tip_list = sorted(seats, key=lambda s: -s["tipping"])

    results = read_csv("legislative_results.csv"); cands = read_csv("legislative_candidates.csv")
    hist, hist_c = {}, {}
    if results is not None:
        for _, r in results.iterrows():
            hist.setdefault(r["key"], []).append({"year": int(r["year"]), "seats": int(r["seats"]), "n_d": int(r["n_d"]), "n_r": int(r["n_r"]), "d_seats": int(r["d_seats"]), "r_seats": int(r["r_seats"]),
                                                   "margin": None if pd.isna(r["party_margin"]) else float(r["party_margin"]), "contested": str(r["contested"]) == "True"})
        for k in hist: hist[k].sort(key=lambda h: -h["year"])
    if cands is not None:
        for _, c in cands.iterrows():
            hist_c.setdefault((c["key"], int(c["year"])), []).append({"party": c["party"], "name": c["candidate"], "votes": None if pd.isna(c["votes"]) else int(c["votes"]), "won": str(c["won"]) == "True", "incumbent": str(c["incumbent_pre"]) == "True"})
        for k in hist_c: hist_c[k].sort(key=lambda c: -(c["votes"] or 0))
    changelog_md = (ROOT / "CHANGELOG.md").read_text() if (ROOT / "CHANGELOG.md").exists() else "# Changelog\n"
    methodology_md = (ROOT / "docs" / "methodology.md").read_text() if (ROOT / "docs" / "methodology.md").exists() else "# Methodology\n"
    sources_md = (ROOT / "docs" / "sources.md").read_text() if (ROOT / "docs" / "sources.md").exists() else ""
    audit_md = (ROOT / "docs" / "DATA_AUDIT.md").read_text() if (ROOT / "docs" / "DATA_AUDIT.md").exists() else ""
    jenv = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=False)
    jenv.globals.update(fmt_m=fmt_m, fmt_pm=fmt_pm, race_label=lambda r: RACE_LABEL.get(r, r), source_label=lambda s: SOURCE_LABEL.get(s, s),
                        adj_label=lambda a: ADJ_LABEL.get(a, a), rating_order=RATING_ORDER, region_label=lambda r: region_label.get(r, r))
    config_yaml = (ROOT / "config" / "model_config.yaml").read_text()
    ctx = dict(f=f, cfg=cfg, chambers=chambers, config_yaml=config_yaml, summary_json=summary_json, flips=flips, closest=closest, house_moves=house_moves, house_closest=house_closest,
               by_rating=by_rating, tipping=tip_list, env_polls=env_polls, bt=bt, misses=misses, changelog_html=md_to_html(changelog_md),
               methodology_html=md_to_html(methodology_md), sources_html=md_to_html(sources_md), audit_html=md_to_html(audit_md))
    SITE.mkdir(exist_ok=True); (SITE / "districts").mkdir(exist_ok=True); (SITE / "data").mkdir(exist_ok=True)
    for page in ("index", "seats", "tipping", "environment", "backtest", "methodology", "changelog", "sources"):
        html = jenv.get_template(f"{page}.html").render(page=page, rel="", **ctx)
        (SITE / f"{page}.html").write_text(html)
    tpl = jenv.get_template("district.html")
    for s in seats:
        html = tpl.render(page="district", rel="../", s=s, b=s["breakdown"], hist=hist.get(s["key"], []), hist_c=hist_c, **ctx)
        (SITE / "districts" / f"{s['seat']}.html").write_text(html)
    tpl_h = jenv.get_template("house_district.html")
    for d in hd:
        html = tpl_h.render(page="district", rel="../", d=d, b=d["breakdown"], hist=hist.get(d["key"], []), hist_c=hist_c, **ctx)
        (SITE / "districts" / f"{d['key']}.html").write_text(html)
    shutil.copy(OUTPUT / "forecast.json", SITE / "data" / "forecast.json")
    for fn in ("senate_seats.csv", "house_districts.csv", "backtest.json"):
        if (OUTPUT / fn).exists(): shutil.copy(OUTPUT / fn, SITE / "data" / fn)
    (SITE / ".nojekyll").write_text("")
    print(f"[site] wrote {len(seats)} Senate pages, {len(hd)} House district pages and 8 top-level pages to {SITE}")


if __name__ == "__main__":
    main()
