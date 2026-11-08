"""Nightly: append yesterday's (and any missing recent days') actual train times from Trafikverket.

Keeps one file per route: data/trv/<route>.json with every advertised train at both stations.
Trafikverket only keeps a few days of history, so this job must run daily.
"""
import json, os, sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from trv_route import signature, announcements

ROUTES = {"goteborg-trollhattan": ("Göteborg C", "Trollhättan C"), "malmo-almhult": ("Malmö C", "Älmhult"), "stockholm-uppsala": ("Stockholm C", "Uppsala C"), "stockholm-strangnas": ("Stockholm C", "Strängnäs")}
OUT = Path(__file__).resolve().parents[1] / "data" / "trv"
OUT.mkdir(parents=True, exist_ok=True)
today = date.today()
for slug, (a_name, b_name) in ROUTES.items():
    f = OUT / f"{slug}.json"
    doc = json.loads(f.read_text()) if f.exists() else {"stations": [a_name, b_name], "days": {}}
    a, b = signature(a_name), signature(b_name)
    doc["signatures"] = [a, b]
    for back in range(3, 0, -1):  # the last 3 days, so a missed night is filled in
        d = today - timedelta(days=back)
        if d.isoformat() in doc["days"]:
            continue
        n = d + timedelta(days=1)
        day = {"a_dep": announcements(a, "Avgang", d, n), "a_arr": announcements(a, "Ankomst", d, n),
               "b_dep": announcements(b, "Avgang", d, n), "b_arr": announcements(b, "Ankomst", d, n)}
        if day["a_dep"]:
            doc["days"][d.isoformat()] = day
            print(slug, d, {k: len(v) for k, v in day.items()}, flush=True)
    f.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
