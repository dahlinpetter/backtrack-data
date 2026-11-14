"""Data health: is every day of the last two months covered, and are the 20-minute jobs still running?

Writes data/health.json, shown at the top of the server's /stats page.
- history (official archive) is the reference; a normal weekday has ~450 trains
- the archive can lag up to ~2 weeks, so a missing day is only a problem after 14 days,
  unless the live log also has too little for it
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1] / "data"
TZ = ZoneInfo("Europe/Stockholm")
FULL = 300          # trains per weekday we call complete (normal is ~440-490)
FULL_WEEKEND = 150  # weekends run fewer trains
STALE_MIN = 90      # the 20-minute jobs (Any trip, Danish arrivals) must have saved within this
LAG_DAYS = 14       # how long we wait for the archive before calling a day a gap


def counts(name):
    p = ROOT / name
    if not p.exists():
        return {}, None
    doc = json.loads(p.read_text())
    c = {}
    for t in doc.get("trains", []):
        c[t["d"]] = c.get(t["d"], 0) + 1
    return c, doc.get("updated")


def numbers(name_or_path):
    p = name_or_path if isinstance(name_or_path, Path) else ROOT / name_or_path
    if not p.exists():
        return {}
    doc = json.loads(p.read_text())
    out = {}
    for t in doc.get("trains", []):
        sw = [x for x in t["s"] if x[0] <= 3 and len(x) < 6]  # stops Trafikverket reports itself (Lund C..Hyllie)
        if len(sw) >= 2:
            out.setdefault(t["d"], set()).add(str(t["n"]))
    return out


def main():
    hist, hist_upd = counts("history.json")
    live, live_upd = counts("delays.json")
    anyc = {}
    for f in (ROOT / "anytrip").glob("*.json"):
        try:
            anyc[f.stem] = len(json.loads(f.read_text()).get("trains", []))
        except Exception:
            pass
    today = datetime.now(TZ).date()
    days, problems, waiting = [], [], []
    d = today - timedelta(days=61)
    while d < today:
        k = d.isoformat(); h = hist.get(k, 0); l = live.get(k, 0); a = anyc.get(k, 0); age = (today - d).days
        full = FULL if d.weekday() < 5 else FULL_WEEKEND
        if h >= full:
            state = "ok"
        elif a >= full:
            state = "recent"      # archive not in yet; Trafikverket's every-train file has the day
        elif l >= full:
            state = "live"        # archive not in yet, but the live log has the day
        elif age <= LAG_DAYS:
            state = "waiting"     # will fill in when the archive publishes
            waiting.append(k)
        else:
            state = "gap"
            problems.append(f"{k}: only {max(h, l, a)} trains saved and the archive never came")
        days.append({"d": k, "hist": h, "live": l, "any": a, "state": state})
        d += timedelta(days=1)
    # cross-check: two independent sources for the same day must agree on which trains ran
    hist_n = numbers("history.json")
    cross = []
    for f in sorted((ROOT / "anytrip").glob("*.json")):
        k = f.stem
        if k not in hist_n:
            continue
        tv = numbers(f).get(k, set())
        miss_hist, miss_tv = sorted(tv - hist_n[k]), sorted(hist_n[k] - tv)
        cross.append({"d": k, "trafikverket": len(tv), "archive": len(hist_n[k]), "only_trafikverket": miss_hist[:40], "only_archive": miss_tv[:40]})
        if len(miss_hist) > 0.05 * max(1, len(tv)):
            problems.append(f"{k}: the archive is missing {len(miss_hist)} of {len(tv)} trains Trafikverket saw (e.g. {', '.join(miss_hist[:5])})")
    now = datetime.now(TZ)
    def stale(label, iso):
        if not iso:
            problems.append(f"{label}: never saved")
            return
        mins = (now - datetime.fromisoformat(iso).replace(tzinfo=TZ)).total_seconds() / 60
        if mins > STALE_MIN:
            problems.append(f"{label}: last saved {iso[11:16]} {iso[:10]}, {int(mins)} min ago")
    tf = ROOT / "anytrip" / f"{today}.json"
    stale("Any trip (every train, Trafikverket)", json.loads(tf.read_text()).get("updated") if tf.exists() else None)
    stale("Live log incl. Danish arrivals", live_upd)
    doc = {"updated": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M"), "history_updated": hist_upd, "live_updated": live_upd,
           "ok": not problems, "problems": problems, "cross": cross, "waiting": waiting, "days": days}
    (ROOT / "health.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(f"health: {len(problems)} problems, {len(waiting)} waiting for the archive")
    for p_ in problems:
        print(f"::error::{p_}")
    # morning report: yesterday, source by source, on the run's summary page
    y = (today - timedelta(days=1)).isoformat()
    yd = next((x for x in days if x["d"] == y), {})
    yc = next((x for x in cross if x["d"] == y), None)
    rep = [f"## Data report for {y}", "",
           f"- Trafikverket (every train): {yd.get('any', 0)} trains",
           f"- Live log: {yd.get('live', 0)} trains",
           f"- Official archive: {yd.get('hist', 0)} trains" + ("" if yd.get("hist") else " (not published yet, normal for a few days)"),
           f"- Day status: {yd.get('state', 'unknown')}"]
    if yc:
        rep.append(f"- Cross-check: archive missing {len(yc['only_trafikverket'])}, Trafikverket missing {len(yc['only_archive'])}")
    rep += ["", "### Problems" if problems else "### No problems", *[f"- {p_}" for p_ in problems]]
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write("\n".join(rep) + "\n")
    print("\n".join(rep))
    # --strict (the data watch job): fail the run, so GitHub emails the owner
    if "--strict" in sys.argv and problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
