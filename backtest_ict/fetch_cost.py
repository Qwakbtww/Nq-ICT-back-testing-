"""Check Databento cost/size for MNQ 1m bars (metadata only, free). Key read from DATABENTO_KEY_FILE; never printed."""
import os, sys, databento as db
key = open(os.environ["DATABENTO_KEY_FILE"]).read().strip()
c = db.Historical(key)
start, end = sys.argv[1], sys.argv[2]
for symbols, stype in [(["MNQ.FUT"], "parent"), (["MNQ.v.0", "MNQ.v.1"], "continuous")]:
    cost = c.metadata.get_cost(dataset="GLBX.MDP3", schema="ohlcv-1m", symbols=symbols, stype_in=stype, start=start, end=end)
    size = c.metadata.get_billable_size(dataset="GLBX.MDP3", schema="ohlcv-1m", symbols=symbols, stype_in=stype, start=start, end=end)
    print(symbols, stype, f"cost=${cost:.4f}", f"size={size/1e6:.1f}MB")
print(c.metadata.get_dataset_range(dataset="GLBX.MDP3"))
