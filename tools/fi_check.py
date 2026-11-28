"""Finland check: share of VR commuter trains per line and month that were cancelled or arrived >10 min late at the last station.
Data: Fintraffic Digitraffic (open, CC BY 4.0, no key). Run by .github/workflows/fi-check.yml.
VR's season-ticket rule: a month qualifies if cancelled + >10 min late trains exceed 10% of all services that month."""
import json, time, urllib.request, gzip, collections, sys
from datetime import date, timedelta
start, end = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
H = {"Digitraffic-User": "backtrack-fi-check", "Accept-Encoding": "gzip"}
m = collections.defaultdict(lambda: collections.Counter())
d = start
while d <= end:
    for attempt in range(4):
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"https://rata.digitraffic.fi/api/v1/trains/{d}", headers=H), timeout=120)
            b = r.read(); trains = json.loads(gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b); break
        except Exception as e:
            print(d, "retry", e, flush=True); time.sleep(10)
    else:
        trains = []
    for t in trains:
        line = t.get("commuterLineID") or ""
        if t.get("trainCategory") != "Commuter" or not line:
            continue
        rows = [x for x in t["timeTableRows"] if x.get("trainStopping", True)]
        if not rows:
            continue
        last = [x for x in rows if x["type"] == "ARRIVAL"][-1:] or rows[-1:]
        last = last[0]
        k = (d.strftime("%Y-%m"), line)
        m[k]["trains"] += 1
        if t.get("cancelled") or last.get("cancelled"):
            m[k]["cancelled"] += 1
        elif (last.get("differenceInMinutes") or 0) > 10:
            m[k]["late10"] += 1
        if not t.get("cancelled") and not last.get("cancelled") and max((x.get("differenceInMinutes") or 0) for x in rows) > 10:
            m[k]["late10any"] += 1  # stricter reading: more than 10 min late at any station on the way
        if not t.get("cancelled") and (last.get("differenceInMinutes") or 0) >= 20:
            m[k]["late20"] += 1
    print(d, len(trains), flush=True)
    d += timedelta(days=1); time.sleep(1.2)
out = [{"month": k[0], "line": k[1], **v, "share": round(100 * (v["cancelled"] + v["late10"]) / v["trains"], 1),
        "share_any": round(100 * (v["cancelled"] + v["late10any"]) / v["trains"], 1)} for k, v in sorted(m.items())]
for o in out:
    print(o, flush=True)
import os; os.makedirs("data/fi", exist_ok=True)
json.dump(out, open(f"data/fi/check_{start}_{end}.json", "w"), indent=0)
