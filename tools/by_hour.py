"""Late trains and potential claims per commuting hour, Malmö C <-> København H.

Same counting as the Backtrack app: weekdays only, a train counts as late when it
arrives 20+ min late at the destination (a cancelled train counts by when the next
train arrived). Claim values: 2,670 kr 30-day ticket (trip = price/20), 50/75/100 %
at 20/40/60 min; "code" = taken as a Skånetrafiken discount code (+50 %).
Writes data/by_hour.json with: last 30 days, last 2 months, and each calendar month.
"""
import json, datetime
h = json.load(open("data/page_history.json")); l = json.load(open("data/delays.json"))
TICKET = 2670; TV = TICKET / 20
OUT = [(5.5, 6.5), (6.5, 7.5), (7.5, 8.5), (8.5, 9.5), (9.5, 10.5)]
HOME = [(14.5, 15.5), (15.5, 16.5), (16.5, 17.5), (17.5, 18.5), (18.5, 19.5)]
lv = lambda e: 100 if e >= 60 else 75 if e >= 40 else 50 if e >= 20 else 0

def bydays(doc):
    S = doc["stops"]; out = {}
    for t in doc["trains"]: out.setdefault(t["d"], []).append((t, S))
    return out
H, Lv = bydays(h), bydays(l)
ALL = sorted(d for d in set(H) | set(Lv) if datetime.date.fromisoformat(d).weekday() < 5)

def J(day, f, to):
    src = H.get(day, []) if len(H.get(day, [])) >= len(Lv.get(day, [])) else Lv.get(day, [])
    out = []; seen = set()
    for t, S in src:
        if f not in S or to not in S: continue
        s = t["s"]; fi, ti = S.index(f), S.index(to)
        a = [x for x in s if x[0] == fi]; b = [x for x in s if x[0] == ti]
        if not a or not b or s.index(b[0]) <= s.index(a[0]): continue
        k = (a[0][1], b[0][3])
        if k in seen: continue
        seen.add(k); out.append(dict(dep=a[0][1], arr=b[0][3], delay=b[0][2], c=bool(t["c"])))
    out.sort(key=lambda j: j["dep"])
    for j in out:
        if not j["c"]: j["eff"] = j["delay"]; continue
        nx = next((k for k in out if k["dep"] > j["dep"] and not k["c"]), None)
        j["eff"] = max(0, nx["arr"] + nx["delay"] - j["arr"]) if nx else 60
    return out

def table(days, f, to, wins):
    rows = []
    for a, b in wins:
        n = late = bad = 0; worst = avg = 0.0
        for d in days:
            js = [j for j in J(d, f, to) if a * 60 <= j["dep"] < b * 60]
            n += len(js); late += sum(1 for j in js if j["eff"] >= 20)
            if js:
                m = max(lv(j["eff"]) for j in js); worst += TV * m / 100; bad += m > 0
                avg += sum(TV * lv(j["eff"]) / 100 for j in js) / len(js)
        hm = lambda x: f"{int(x):02d}:{int(round(x % 1 * 60)):02d}"
        rows.append(dict(window=f"{hm(a)}-{hm(b)}", trains=n, late=late, share=round(100 * late / max(n, 1), 1),
                         days_with_claim=bad, typical_cash=round(avg), typical_code=round(avg * 1.5),
                         up_to_cash=round(worst), up_to_code=round(worst * 1.5)))
    return rows

def period(days):
    return dict(first=days[0], last=days[-1], weekdays=len(days),
                to_work=table(days, "Malmö C", "København H", OUT), home=table(days, "København H", "Malmö C", HOME))

end = ALL[-1]; e = datetime.date.fromisoformat(end)
res = dict(updated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), ticket=TICKET, periods={})
res["periods"]["last_30_days"] = period([d for d in ALL if d > (e - datetime.timedelta(days=30)).isoformat()])
res["periods"]["last_2_months"] = period([d for d in ALL if d > (e - datetime.timedelta(days=61)).isoformat()])
for m in sorted({d[:7] for d in ALL}):
    ds = [d for d in ALL if d.startswith(m)]
    if len(ds) >= 10: res["periods"][m] = period(ds)
json.dump(res, open("data/by_hour.json", "w"), ensure_ascii=False, indent=1)
print("by_hour:", ", ".join(f"{k} ({v['weekdays']} days)" for k, v in res["periods"].items()))
