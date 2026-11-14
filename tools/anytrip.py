"""Every train on the Lund–Malmö–Copenhagen stretch, all day, every day, from Trafikverket's open API.

Feeds the app's "Any trip" lookup for days the KoDa history doesn't cover yet (it lags a week or more),
and for evenings and weekends the live log never sees.

    TRAFIKVERKET_KEY=... python tools/anytrip.py            # today and yesterday (Swedish time)
    TRAFIKVERKET_KEY=... python tools/anytrip.py 70         # backfill: the last 70 days, skipping days already saved

Writes data/anytrip/YYYY-MM-DD.json in the same shape as delays.json:
  {"day", "updated", "stops", "trains": [{"d","n","c","s":[[stop, sched_arr, arr_delay, sched_dep, dep_delay], ...]}]}
Times are minutes after midnight on the train's day; delays are minutes, or null when the train hasn't got there yet.
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
                                                          "ActivityType", "LocationSignature", "ScheduledDepartureDateTime"])
    q = (f'<QUERY objecttype="TrainAnnouncement" schemaversion="1.9" limit="20000"><FILTER><AND><OR>{locs}</OR>'
         f'<EQ name="Advertised" value="true"/><GTE name="AdvertisedTimeAtLocation" value="{d}T00:00:00"/>'
         f'<LT name="AdvertisedTimeAtLocation" value="{n}T00:00:00"/></AND></FILTER>{inc}</QUERY>')
    return ask(q).get("TrainAnnouncement", [])


def build(sig, d, rows):
    trains = {}
    for r in rows:
        day = (r.get("ScheduledDepartureDateTime") or r["AdvertisedTimeAtLocation"])[:10]
        t = trains.setdefault((day, r["AdvertisedTrainIdent"]), {"d": day, "n": r["AdvertisedTrainIdent"], "c": 0, "_s": {}})
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
            s.append([i, sa, ad, sd, dd])
        s.sort(key=lambda x: x[3])
        out.append({"d": t["d"], "n": t["n"], "c": t["c"], "s": s})
    out.sort(key=lambda t: t["s"][0][3])
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
