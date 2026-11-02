"""Append an automatic run entry to CHANGELOG.md (idempotent per as_of date + numbers)."""
from __future__ import annotations

import json

from .common import OUTPUT, ROOT


def main():
    f = json.loads((OUTPUT / "forecast.json").read_text())
    env = f["environment"]
    n_polls = sum(v["n_polls"] for v in env["sources"].values())
    parts = []
    for ch, label in (("senate", "Senate"), ("house", "House")):
        if ch in f["chambers"]:
            c = f["chambers"][ch]
            parts.append(f"{label}: D control {c['p_dem_control']*100:.0f}%, mean {c['dem_seats_mean']:.1f} D seats of {c['total_seats']}.")
    line = (f"- **{f['as_of']} model run** — " + " ".join(parts) +
            f" Statewide generic legislative margin {'D' if env['generic_legislative_margin']>0 else 'R'}+{abs(env['generic_legislative_margin']):.1f} "
            f"from {n_polls} polls. {f['n_sims']:,} simulations.")
    p = ROOT / "CHANGELOG.md"
    text = p.read_text() if p.exists() else "# Changelog\n\n## Model runs\n\n## Changes to model, config, or data\n"
    if line in text:
        return
    marker = "## Model runs\n"
    text = text.replace(marker, marker + "\n" + line + "\n", 1) if marker in text else text + "\n" + marker + "\n" + line + "\n"
    p.write_text(text)
    print("[changelog] appended run entry")


if __name__ == "__main__":
    main()
