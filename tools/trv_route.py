"""Fetch actual departure/arrival times between two stations from Trafikverket's open API.

    TRAFIKVERKET_KEY=... python tools/trv_route.py "Göteborg C" "Trollhättan C" 2026-09-07 2026-11-06 data/trollhattan_trv.json
Writes every advertised train (both directions) with planned/actual times at both stations.
"""
import json, os, sys, urllib.request, urllib.error
from datetime import date, timedelta

URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"
KEY = os.environ.get("TRAFIKVERKET_KEY", "").strip()


def ask(query):
    body = f'<REQUEST><LOGIN authenticationkey="{KEY}"/>{query}</REQUEST>'.encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "text/xml"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read())["RESPONSE"]["RESULT"][0]
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace").replace(KEY, "***")
        raise RuntimeError(f"HTTP {e.code}: {msg[:600]}")
    if "ERROR" in res:
        raise RuntimeError(res["ERROR"])
    return res


def signature(name):
    q = f'<QUERY objecttype="TrainStation" schemaversion="1.4"><FILTER><EQ name="AdvertisedLocationName" value="{name}"/></FILTER><INCLUDE>LocationSignature</INCLUDE><INCLUDE>AdvertisedLocationName</INCLUDE></QUERY>'
    st = ask(q).get("TrainStation", [])
    if not st and name.endswith(" C"):
        return signature(name[:-2])  # Trafikverket names some stations without " C"
    if not st:
        raise SystemExit(f"Station not found: {name}")
    print(name, "->", st[0]["LocationSignature"], flush=True)
    return st[0]["LocationSignature"]


FIELDS = ["AdvertisedTrainIdent", "AdvertisedTimeAtLocation", "TimeAtLocation", "Canceled", "ActivityType",
          "LocationSignature", "ScheduledDepartureDateTime", "InformationOwner", "ProductInformation", "ToLocation", "FromLocation"]


def announcements(sig, activity, d0, d1):
    inc = "".join(f"<INCLUDE>{f}</INCLUDE>" for f in FIELDS)
    q = (f'<QUERY objecttype="TrainAnnouncement" schemaversion="1.9" limit="20000"><FILTER><AND>'
         f'<EQ name="LocationSignature" value="{sig}"/><EQ name="ActivityType" value="{activity}"/><EQ name="Advertised" value="true"/>'
         f'<GTE name="AdvertisedTimeAtLocation" value="{d0}T00:00:00"/><LT name="AdvertisedTimeAtLocation" value="{d1}T00:00:00"/>'
         f'</AND></FILTER>{inc}</QUERY>')
    return ask(q).get("TrainAnnouncement", [])


def main(a_name, b_name, start, end, out):
    a, b = signature(a_name), signature(b_name)
    s, e = date.fromisoformat(start), date.fromisoformat(end) + timedelta(days=1)
    rows = {k: [] for k in ("a_dep", "a_arr", "b_dep", "b_arr")}
    d = s
    while d < e:
        n = min(d + timedelta(days=7), e)
        rows["a_dep"] += announcements(a, "Avgang", d, n); rows["a_arr"] += announcements(a, "Ankomst", d, n)
        rows["b_dep"] += announcements(b, "Avgang", d, n); rows["b_arr"] += announcements(b, "Ankomst", d, n)
        print(d, {k: len(v) for k, v in rows.items()}, flush=True)
        d = n
    first = min((r["AdvertisedTimeAtLocation"] for r in rows["a_dep"]), default=None)
    print("earliest record returned:", first, flush=True)
    json.dump({"stations": [a_name, b_name], "signatures": [a, b], "range": [start, end], **rows},
              open(out, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main(*sys.argv[1:6])
