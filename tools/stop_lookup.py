"""Print Trafiklab stop groups for station names (to pin ids in config.json)."""
import os, sys, urllib.parse
sys.path.insert(0, ".")
import collect
key = os.environ["TRAFIKLAB_KEY"].strip()
for name in sys.argv[1:]:
    res = collect.http_get_json(f"{collect.API}/stops/name/{urllib.parse.quote(name)}?key={key}")
    for g in res.get("stop_groups", [])[:6]:
        print(f"{name!r}: {g['name']} | {g['id']} | {g.get('area_type')} | {g.get('transport_modes')}", flush=True)
