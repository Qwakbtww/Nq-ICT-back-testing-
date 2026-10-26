"""Build the back-adjusted MNQ 1m series and roll_log.csv offline from the raw Databento file.

Roll rule (volume-based, decided only with information available at the time):
  * session date = CT date of (timestamp + 7h), so a session runs 17:00 CT -> 16:00 CT.
  * the contract traded in session D is the outright with the highest total volume in
    session D-1; the front never moves back to an earlier expiry.
  * roll time = first bar of the first session on the new contract (17:00 CT open).
  * adjustment = close(new) - close(old) at the last 1m timestamp of session D-1 where
    both contracts printed a bar. Adjustment is additive (point distances are preserved)
    and accumulated backwards, so the latest contract is unadjusted.

Outputs (in ./data):
  roll_log.csv          one row per roll
  mnq_1m_adj.parquet    ts (UTC, ns), open, high, low, close, volume, contract
"""
import os
import numpy as np
import pandas as pd
import databento as db

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw", "MNQ_FUT_ohlcv1m_2019-05-01_2026-10-24.dbn.zst")
OUT_1M = os.path.join(HERE, "data", "mnq_1m_adj.parquet")
OUT_ROLL = os.path.join(HERE, "data", "roll_log.csv")
TZ = "America/Chicago"
MONTHS = {"H": 3, "M": 6, "U": 9, "Z": 12}


def expiry_key(sym):
    """MNQZ9 -> (2019, 12); single-digit years are mapped into 2019..2028."""
    m, y = sym[3], int(sym[4:])
    year = 2010 + y if y >= 9 else 2020 + y
    return (year, MONTHS[m])


def session_date(ts_utc):
    ct = ts_utc.tz_convert(TZ)
    return (ct + pd.Timedelta(hours=7)).tz_localize(None).normalize()


def main():
    raw = db.DBNStore.from_file(RAW).to_df(price_type="float", pretty_ts=True, map_symbols=True)
    raw = raw[~raw["symbol"].str.contains("-")]                          # outrights only
    raw = raw[["open", "high", "low", "close", "volume", "symbol"]].copy()
    raw.index = pd.DatetimeIndex(raw.index).as_unit("ns")                 # explicit ns unit
    assert str(raw.index.dtype) == "datetime64[ns, UTC]"
    raw["sdate"] = session_date(raw.index)

    # session volume per contract -> contract for each session (decided from the prior session)
    vol = raw.groupby(["sdate", "symbol"])["volume"].sum().unstack(fill_value=0)
    sessions = vol.index
    chosen = {}
    current = None
    for i, d in enumerate(sessions):
        if i == 0:
            current = vol.iloc[0].idxmax()
        else:
            leader = vol.iloc[i - 1].idxmax()
            if expiry_key(leader) > expiry_key(current):                  # never roll backwards
                current = leader
        chosen[d] = current
    chosen = pd.Series(chosen)

    front = raw[raw["symbol"].values == chosen.reindex(raw["sdate"]).values].copy()

    # roll log + additive back-adjustment
    rolls = []
    for i in range(1, len(sessions)):
        d_prev, d = sessions[i - 1], sessions[i]
        old, new = chosen[d_prev], chosen[d]
        if old == new:
            continue
        prev = raw[raw["sdate"] == d_prev]
        a = prev[prev["symbol"] == old]["close"]
        b = prev[prev["symbol"] == new]["close"]
        common = a.index.intersection(b.index)
        assert len(common) > 0, f"no common bar for roll {old}->{new} on {d_prev}"
        t_ref = common.max()
        first_bar = front[front["sdate"] == d].index.min()
        rolls.append(dict(roll_ts_utc=first_bar, roll_ts_ct=first_bar.tz_convert(TZ),
                          session_date=d.date(), old=old, new=new, ref_ts_utc=t_ref,
                          old_close=a[t_ref], new_close=b[t_ref], diff=b[t_ref] - a[t_ref]))
    roll_log = pd.DataFrame(rolls)

    adj = np.zeros(len(front))
    for r in roll_log.itertuples():
        adj[front.index < r.roll_ts_utc] += r.diff
    roll_log["cum_adj_before"] = [adj[front.index < t].max() if (front.index < t).any() else 0.0
                                  for t in roll_log["roll_ts_utc"]]
    for col in ["open", "high", "low", "close"]:
        front[col] = (front[col] + adj).round(2)
    # every price must remain on the 0.25 tick grid
    assert np.allclose((front[["open", "high", "low", "close"]].values * 4) % 1, 0)

    out = front.drop(columns=["sdate"]).rename(columns={"symbol": "contract"})
    out.index.name = "ts"
    out.to_parquet(OUT_1M)
    roll_log.to_csv(OUT_ROLL, index=False)
    print(f"1m bars: {len(out):,}  from {out.index.min()} to {out.index.max()}")
    print(f"rolls: {len(roll_log)}")
    print(roll_log[["roll_ts_ct", "old", "new", "diff"]].to_string(index=False))


if __name__ == "__main__":
    main()
