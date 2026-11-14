"""Every train on the Lund–Malmö–Copenhagen stretch, all day, every day, from Trafikverket's open API.

Feeds the app's "Any trip" lookup for days the KoDa history doesn't cover yet (it lags a week or more),
and for evenings and weekends the live log never sees.

    TRAFIKVERKET_KEY=... python tools/anytrip.py            # today and yesterday (Swedish time)
    TRAFIKVERKET_KEY=... python tools/anytrip.py 70         # backfill: the last 70 days, skipping days already saved

Writes data/anytrip/YYYY-MM-DD.json in the same shape as delays.json:
  {"day", "updated", "stops", "trains": [{"d","n","c","s":[[stop, sched_arr, arr_delay, sched_dep, dep_delay], ...]}]}
Times are minutes after midnight on the train's day; delays are minutes, or null when the train hasn't got there yet.
Trafikverket only reports Swedish stations. For trains that run to or from Denmark, Kastrup, Ørestad and København H are
added from the usual running time to Hyllie (learned from the KoDa history), with the delay measured at Hyllie; such stops
carry a 6th value 1 ("estimated").
Files older than KEEP_DAYS are deleted.
"""
import json, sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).parent))
from trv_route import ask

TZ = ZoneInfo("Europe/Stockholm")
STOPS = ["Lund C", "Malmö C", "Triangeln", "Hyllie", "Kastrup", "Ørestad", "København H"]  # same order as delays.json
NAMES = {"Lund C": ["Lund C", "Lund"], "Malmö C": ["Malmö C", "Malmö"], "Triangeln": ["Triangeln", "Malmö Triangeln"],
         "Hyllie": ["Hyllie"], "Kastrup": ["Kastrup", "Københavns Lufthavn", "Kastrup lufthavn"], "Ørestad": ["Ørestad"],
         "København H": ["København H", "Köpenhamn H", "København"]}
KEEP_DAYS = 75
HYLLIE = STOPS.index("Hyllie")
# minutes between Hyllie and each Danish stop: (towards Denmark, towards Sweden), median from the KoDa history
DK_OFFSET = {STOPS.index("Kastrup"): (14, 12), STOPS.index("Ørestad"): (21, 20), STOPS.index("København H"): (29, 28)}
OUT = Path(__file__).resolve().parents[1] / "data" / "anytrip"
OUT.mkdir(parents=True, exist_ok=True)


def signatures():
    sig = {}
    for stop, names in NAMES.items():
        for nm in names:
            q = (f'<QUERY objecttype="TrainStation" schemaversion="1.4"><FILTER><EQ name="AdvertisedLocationName" value="{nm}"/></FILTER>'
                 f'<INCLUDE>LocationSignature</INCLUDE></QUERY>')
            st = ask(q).get("TrainStation", [])
            if st:
                sig[st[0]["LocationSignature"]] = STOPS.index(stop)
                print(f"{stop}: {st[0]['LocationSignature']}", flush=True)
                break
        else:
            print(f"{stop}: not in Trafikverket's station list, skipped", flush=True)
    return sig


def fetch(sig, d):
    """All advertised arrivals and departures at our stops whose advertised time falls on day d (local)."""
    n = d + timedelta(days=1)
    locs = "".join(f'<EQ name="LocationSignature" value="{s}"/>' for s in sig)
    inc = "".join(f"<INCLUDE>{f}</INCLUDE>" for f in ["AdvertisedTrainIdent", "AdvertisedTimeAtLocation", "TimeAtLocation", "Canceled",
                                                          "ActivityType", "LocationSignature", "ScheduledDepartureDateTime", "FromLocation", "ToLocation"])
    q = (f'<QUERY objecttype="TrainAnnouncement" schemaversion="1.9" limit="20000"><FILTER><AND><OR>{locs}</OR>'
         f'<EQ name="Advertised" value="true"/><GTE name="AdvertisedTimeAtLocation" value="{d}T00:00:00"/>'
         f'<LT name="AdvertisedTimeAtLocation" value="{n}T00:00:00"/></AND></FILTER>{inc}</QUERY>')
    return ask(q).get("TrainAnnouncement", [])


def build(sig, d, rows):
    trains = {}
    for r in rows:
        day = (r.get("ScheduledDepartureDateTime") or r["AdvertisedTimeAtLocation"])[:10]
        t = trains.setdefault((day, r["AdvertisedTrainIdent"]), {"d": day, "n": r["AdvertisedTrainIdent"], "c": 0, "_s": {}, "dk": None})
        locs = lambda k: [x.get("LocationName", "") for x in r.get(k, [])]
        if any(x.startswith("Dk.") for x in locs("ToLocation")):
            t["dk"] = "to"
        elif any(x.startswith("Dk.") for x in locs("FromLocation")):
            t["dk"] = "from"
        adv = datetime.fromisoformat(r["AdvertisedTimeAtLocation"])
        mins = adv.hour * 60 + adv.minute + (date.fromisoformat(adv.date().isoformat()) - date.fromisoformat(day)).days * 1440
        delay = None
        if r.get("TimeAtLocation"):
            delay = round((datetime.fromisoformat(r["TimeAtLocation"]) - adv).total_seconds() / 60)
        if r.get("Canceled"):
            t["c"] = 1
        st = t["_s"].setdefault(sig[r["LocationSignature"]], [None, None, None, None])
        if r["ActivityType"] == "Ankomst":
            st[0], st[1] = mins, delay
        else:
            st[2], st[3] = mins, delay
    out = []
    for t in trains.values():
        if len(t["_s"]) < 2:  # only trains that run between two of our stops
            continue
        s = []
        for i, (sa, ad, sd, dd) in t["_s"].items():
            sa = sa if sa is not None else sd
            sd = sd if sd is not None else sa
            ad = ad if ad is not None else (dd if sa == sd else None)
            dd = dd if dd is not None else ad
            s.append([i, sd, ad, sa, dd])  # same order as delays.json: stop, dep, arr delay, arr, dep delay
        h = next((x for x in s if x[0] == HYLLIE), None)
        if h and t["dk"]:
            for i, (to_dk, to_se) in DK_OFFSET.items():
                if any(x[0] == i for x in s):
                    continue
                if t["dk"] == "to":  # leaves Hyllie for Denmark: arrival there estimated from Hyllie's departure
                    m = h[1] + to_dk
                    s.append([i, m, h[4], m, h[4], 1])
                else:  # comes from Denmark: departure estimated from the arrival at Hyllie
                    m = h[3] - to_se
                    s.append([i, m, None, m, None, 1])
        s.sort(key=lambda x: x[1])
        out.append({"d": t["d"], "n": t["n"], "c": t["c"], "s": s})
    out.sort(key=lambda t: t["s"][0][1])
    return out


def main():
    back = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    today = datetime.now(TZ).date()
    sig = signatures()
    days = [today - timedelta(days=k) for k in range(back, -1, -1)]
    for d in days:
        f = OUT / f"{d}.json"
        if back > 1 and f.exists() and d < today - timedelta(days=1):
            continue
        rows = fetch(sig, d)
        trains = [t for t in build(sig, d, rows) if t["d"] == d.isoformat()]
        if not trains:
            print(d, "no data", flush=True)
            continue
        doc = {"day": d.isoformat(), "updated": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M"), "stops": STOPS, "trains": trains}
        f.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
        print(d, len(rows), "announcements,", len(trains), "trains", flush=True)
    for f in OUT.glob("*.json"):
        if f.stem < (today - timedelta(days=KEEP_DAYS)).isoformat():
            f.unlink()


if __name__ == "__main__":
    main()
