"""One-time download of MNQ 1m OHLCV (all contracts, parent symbology) from Databento.

Run once; the backtest itself only reads the saved file offline.
The API key is read from the file named by DATABENTO_KEY_FILE and is never printed.
Aborts if the quoted cost exceeds COST_CAP.
"""
import os, sys
import databento as db

COST_CAP = 15.00
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw", "MNQ_FUT_ohlcv1m_2019-05-01_2026-10-24.dbn.zst")
REQ = dict(dataset="GLBX.MDP3", schema="ohlcv-1m", symbols=["MNQ.FUT"], stype_in="parent",
           start="2019-05-01", end="2026-10-24")

client = db.Historical(open(os.environ["DATABENTO_KEY_FILE"]).read().strip())
cost = client.metadata.get_cost(**REQ)
print(f"quoted cost ${cost:.4f}")
if cost > COST_CAP:
    sys.exit(f"cost exceeds cap ${COST_CAP}; aborting")
if os.path.exists(OUT):
    sys.exit("file already exists; not downloading again")
client.timeseries.get_range(**REQ, path=OUT)
print("saved", OUT, os.path.getsize(OUT) / 1e6, "MB")
