"""Data health: is every weekday of the last two months covered?

Writes data/health.json, shown at the top of the server's /stats page.
- history (official archive) is the reference; a normal weekday has ~450 trains
- the archive can lag up to ~2 weeks, so a missing day is only a problem after 14 days,
  unless the live log also has too little for it
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1] / "data"
TZ = ZoneInfo("Europe/Stockholm")
FULL = 300          # trains per weekday we call complete (normal is ~440-490)
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


def main():
    hist, hist_upd = counts("history.json")
    live, live_upd = counts("delays.json")
    today = datetime.now(TZ).date()
    days, problems, waiting = [], [], []
    d = today - timedelta(days=61)
    while d < today:
        if d.weekday() < 5:
            k = d.isoformat(); h = hist.get(k, 0); l = live.get(k, 0); age = (today - d).days
            if h >= FULL:
                state = "ok"
            elif l >= FULL:
                state = "live"        # archive not in yet, but the live log has the day
            elif age <= LAG_DAYS:
                state = "waiting"     # archive not in yet and the live log is thin: will fill in
                waiting.append(k)
            else:
                state = "gap"
                problems.append(f"{k}: only {max(h, l)} trains saved and the archive never came")
            days.append({"d": k, "hist": h, "live": l, "state": state})
        d += timedelta(days=1)
    doc = {"updated": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M"), "history_updated": hist_upd, "live_updated": live_upd,
           "ok": not problems, "problems": problems, "waiting": waiting, "days": days}
    (ROOT / "health.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(f"health: {len(problems)} gaps, {len(waiting)} waiting for the archive")


if __name__ == "__main__":
    main()
