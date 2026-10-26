"""Cost check (default) or download (with --confirm) of NEW MNQ 1m data for the forward test.

    python3 backtest_ict_v2/fetch_forward.py 2026-10-24 2027-02-01              # cost only, free
    python3 backtest_ict_v2/fetch_forward.py 2026-10-24 2027-02-01 --confirm --cap 5.00

The key is read from the file named by DATABENTO_KEY_FILE and is never printed. Nothing is downloaded
without --confirm, and nothing above --cap dollars. Files go to ./data_forward/ (repository root).
"""
import argparse
import os
import sys

import databento as db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--cap", type=float, default=5.00)
    a = ap.parse_args()
    req = dict(dataset="GLBX.MDP3", schema="ohlcv-1m", symbols=["MNQ.FUT"], stype_in="parent", start=a.start, end=a.end)
    client = db.Historical(open(os.environ["DATABENTO_KEY_FILE"]).read().strip())
    cost = client.metadata.get_cost(**req)
    size = client.metadata.get_billable_size(**req)
    print(f"quoted cost ${cost:.4f}, billable size {size / 1e6:.1f} MB")
    if not a.confirm:
        print("cost check only; rerun with --confirm (and --cap) to download")
        return
    if cost > a.cap:
        sys.exit(f"cost ${cost:.2f} exceeds cap ${a.cap:.2f}; not downloading")
    os.makedirs(os.path.join(ROOT, "data_forward"), exist_ok=True)
    out = os.path.join(ROOT, "data_forward", f"MNQ_FUT_ohlcv1m_{a.start}_{a.end}.dbn.zst")
    if os.path.exists(out):
        sys.exit("file exists; not downloading again")
    client.timeseries.get_range(**req, path=out)
    print("saved", out)


if __name__ == "__main__":
    main()
