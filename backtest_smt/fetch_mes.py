"""Cost quote (default) or one-time download (--confirm) of MES 1m bars for the SMT study.

The real API key is injected by the session's network proxy (saved credential for
hist.databento.com); this script only passes a dummy key in the format the client expects.
Nothing is downloaded without --confirm, and nothing above --cap dollars (clarification #1: $20).

    python3 backtest_smt/fetch_mes.py              # quote only
    python3 backtest_smt/fetch_mes.py --confirm    # download if quote <= cap
"""
import argparse
import os
import sys

import databento as db

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "raw", "MES_FUT_ohlcv1m_2019-05-01_2026-10-24.dbn.zst")
REQ = dict(dataset="GLBX.MDP3", schema="ohlcv-1m", symbols=["MES.FUT"], stype_in="parent",
           start="2019-05-01", end="2026-10-24")
DUMMY_KEY = "db-" + "X" * 29          # replaced by the proxy; never a real key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--cap", type=float, default=20.0)
    a = ap.parse_args()
    client = db.Historical(DUMMY_KEY)
    cost = client.metadata.get_cost(**REQ)
    size = client.metadata.get_billable_size(**REQ)
    print(f"quoted cost ${cost:.4f}, billable size {size / 1e6:.1f} MB")
    if not a.confirm:
        print("quote only; rerun with --confirm to download")
        return
    if cost > a.cap:
        sys.exit(f"cost ${cost:.2f} exceeds cap ${a.cap:.2f}; not downloading")
    if os.path.exists(OUT):
        sys.exit("file already exists; not downloading again")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    client.timeseries.get_range(**REQ, path=OUT)
    print("saved", OUT, f"{os.path.getsize(OUT) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
