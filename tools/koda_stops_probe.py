"""Probe: does Skånetrafiken's GTFS in KoDa have the Älmhult-line stations, and do trains serve them? Prints counts only."""
import os, sys, csv, tempfile, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import koda_backfill as kb
key = os.environ["KODA_KEY"].strip(); day = sys.argv[1]
work = Path(tempfile.mkdtemp())
arch = work / "s.bin"
if not kb.get(f"{kb.BASE}/gtfs-static/{kb.OPERATOR}?date={day}", key, dest=arch, tries=20, wait=30):
    sys.exit("no static")
d = work / "st"; d.mkdir(); kb.extract(arch, d)
f = lambda n: next(d.rglob(n))
want = ["lund", "eslöv", "höör", "hässleholm", "osby", "älmhult", "malmö central"]
stops = {r["stop_id"]: r["stop_name"] for r in csv.DictReader(open(f("stops.txt"), encoding="utf-8-sig"))}
hit = {k: v for k, v in stops.items() if any(w in v.lower() for w in want)}
print("stops matched:", len(hit)); print(sorted(set(hit.values())))
cnt = collections.Counter()
for r in csv.DictReader(open(f("stop_times.txt"), encoding="utf-8-sig")):
    n = hit.get(r["stop_id"])
    if n: cnt[n] += 1
for k, v in sorted(cnt.items()): print(f"{v:6} stop_times at {k}")
