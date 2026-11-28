"""Which route is a VR commuter line, and how late is it per train? python tools/fi_line.py V 2026-11-20"""
import json, sys, urllib.request, gzip, collections
line, day = sys.argv[1], sys.argv[2]
r = urllib.request.urlopen(urllib.request.Request(f"https://rata.digitraffic.fi/api/v1/trains/{day}", headers={"Digitraffic-User": "backtrack-fi-check", "Accept-Encoding": "gzip"}), timeout=120)
b = r.read(); T = json.loads(gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b)
r2 = urllib.request.urlopen(urllib.request.Request("https://rata.digitraffic.fi/api/v1/metadata/stations", headers={"Digitraffic-User": "backtrack-fi-check", "Accept-Encoding": "gzip"}), timeout=60)
b2 = r2.read(); st = json.loads(gzip.decompress(b2) if r2.headers.get("Content-Encoding") == "gzip" else b2)
name = {s["stationShortCode"]: s["stationName"] for s in st}
routes = collections.Counter()
for t in T:
    if t.get("commuterLineID") != line: continue
    rows = [x for x in t["timeTableRows"] if x.get("trainStopping", True)]
    a, z = rows[0], rows[-1]
    routes[(name.get(a["stationShortCode"], a["stationShortCode"]), name.get(z["stationShortCode"], z["stationShortCode"]))] += 1
    stops = [name.get(x["stationShortCode"], x["stationShortCode"]) for x in rows if x["type"] == "ARRIVAL"]
    print(t["trainNumber"], a["scheduledTime"][11:16], "->", z["scheduledTime"][11:16], "late at end:", z.get("differenceInMinutes"), "cancelled:", t.get("cancelled"), "| stops:", " · ".join(stops[:12]))
print(routes)
