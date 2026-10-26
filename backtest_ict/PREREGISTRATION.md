# MNQ ICT-model study — PRE-REGISTRATION

Status: FROZEN. The SHA-256 of this file is stored in `PREREGISTRATION.sha256`.
The main script must recompute the hash and refuse to run on a mismatch.
Nothing below may be changed after results are seen. Bug fixes go in numbered
`AMENDMENT_NNN.md` files (reason, change, and both the original and amended results).
Any analysis not listed here goes in a section labeled **"exploratory, not evidence"**.

Written 2026-10-26, before any test code was written and before any data was inspected
for this study.

## 0. Scope and default conclusion

- This study tests ONE rigid, mechanical interpretation of each ICT model on MNQ futures.
  It does NOT test how a skilled discretionary trader applies ICT. A negative result does
  not prove discretionary use has no skill. A positive result is only a lead.
- The default conclusion is **"no evidence of an edge"** unless every "candidate edge"
  criterion in §9 is met.

## 1. Data

- Instrument: MNQ, back-adjusted continuous series rebuilt offline from the raw file on disk
  and `roll_log.csv`, using the existing data layer. No API calls.
- Tick = 0.25 pt; $2.00 per point; 1 contract.
- All levels, swings, FVGs, ATR and EMAs are computed from the SAME adjusted series.
- Timestamps: parsed with an explicit nanosecond unit (`datetime64[ns]`), stored in UTC,
  converted to `America/Chicago` with the tz database (this handles DST). NY time = CT + 1h.
- Bars are labeled by their OPEN time. A bar is known only at its close (open + bar length).
- 5m and 1H bars are resampled from the adjusted 1m bars (label=left, closed=left), only
  where 1m bars exist. Partial bars are kept. 1H bars use CT clock hours. No bars exist
  during the 16:00–17:00 CT halt and no bar spans the halt.
- Bar counting ("N bars") always counts existing 5m bars in the series, not clock time.
- Swings, ATR and EMAs run continuously across sessions (no daily reset).
- **Roll exclusion:** a trade is excluded if a roll in `roll_log.csv` falls inside
  [arm time, exit time]. If the log gives only a date, the whole CT calendar date counts as
  the roll period, and any trade whose [arm, exit] interval overlaps that date is excluded.
  Exclusion counts are reported.

## 2. Levels and indicators (all known before use)

- **RTH session** = 5m bars with open time in [08:30, 15:00) CT.
- **PDH/PDL** = high/low of the most recent COMPLETED RTH session (for Monday morning:
  Friday's; for the ASIA window on the evening of day D: day D's RTH that ended at 15:00).
  Usable from 15:00 CT of the session it describes.
- **ONH/ONL** = high/low of bars with open time in [17:00 previous evening, 08:30) CT.
  Usable only from the 08:30 bar onward.
- **ATR** = ATR(14) on 5m bars, Wilder smoothing (RMA) of true range. For any rule applied
  at bar *i*, the ATR used is the value at the close of bar *i−1*.
- **1H bias** = EMA 9/21/50 (pandas `ewm(span, adjust=False)`) on 1H closes, using only 1H
  bars whose close time ≤ the setup's arm time. Bullish if 9 > 21 > 50, bearish if 9 < 21 < 50,
  otherwise neutral. The first 50 1H bars of the series are a warm-up and have no bias.

## 3. Operational definitions (5m bars)

- **Swing high at bar p**: high[p] strictly > high of each of the 3 bars before and 3 bars
  after. Confirmed at the close of bar p+3 and usable only from then. Swing low mirrored.
  Ties do not form swings.
- **Sweep of a high level L at bar s**:
  (a) close[s−1] < L (price approaches from below);
  (b) high[s] ≥ L + 1 tick;
  (c) a bar r ∈ {s, s+1, s+2} closes < L. The first such r is the **reclaim bar**.
  Sweep extreme = max(high[s..r]). Low levels are mirrored.
  If one bar sweeps several same-side levels, one sweep is recorded and labeled with the
  first level in the order PDH, ONH (PDL, ONL for lows). Levels may be swept more than once.
- **Displacement bar d (bearish)**: close[d] < low[d−1] AND close[d] < open[d] AND
  (open[d] − close[d]) ≥ 1.0 × ATR (ATR per §2). Bullish mirrored.
- **MSS after a high sweep at s**: the FIRST bearish displacement bar m with
  s+1 ≤ m ≤ s+12 and m ≥ r, whose close < the reference swing low. The reference swing low
  is the most recent swing low with pivot index p < s and confirmation index p+3 ≤ m−1.
  If no swing low qualifies, there is no MSS. Low sweeps mirrored.
- **FVG**: bar1 = m−1, bar2 = m (MSS bar), bar3 = m+1. Bearish gap: low[bar1] > high[bar3],
  zone [high[bar3], low[bar1]], with gap size ≥ 2.0 pts. Bullish mirrored. Known at the close
  of bar3. If there is no qualifying gap centered on the MSS bar, there is no signal. Other
  FVGs are not searched.
- **Signal** (Models A and B) = sweep → MSS → FVG, known at the close of bar3 (= arm time).
  Signal direction: short after a high sweep, long after a low sweep.

## 4. Models

Price rounding: limit entry prices are rounded to the nearest tick, ties rounded toward the
less favorable side (a sell rounds down, a buy rounds up). Targets are rounded to the tick
nearer the entry. Stops are already on ticks.

**Stale-order rule (all models):** if the close of the arm bar is already beyond the limit
price in the fill direction (the limit is marketable at arm time), the setup is skipped and
counted as "stale".

**Stop-distance filter (all models):** R = |entry − stop| at arm time. Skip if R < 8 or
R > 40 pts. Counted separately as "skip_small" and "skip_large".

### Model A — Sweep + FVG
- Limit at the FVG midpoint, armed at the bar3 close.
- Valid for the 12 5m bars after bar3 (through the close of bar3+12), but never past the
  window end.
- Cancel if price trades ≥ 1 tick beyond the sweep extreme before fill. If the same 1m bar
  reaches both the fill and the cancel condition, assume the FILL happened first (the
  conservative choice, because the stop then also gets checked in that bar).
- Stop = sweep extreme + 3 pts (short) / − 3 pts (long).

### Model B — OTE
- Same signal as A.
- Leg (short case): H = sweep extreme; Lf = lowest low over bars s..m inclusive (the far end).
  Require H − Lf ≥ 20 pts, otherwise skip ("skip_leg").
- Entry = limit at Lf + 0.705 × (H − Lf) (short). Long mirrored: Hf − 0.705 × (Hf − Lsweep).
- Because the signal needs the FVG, the order is ARMED at the bar3 (m+1) close. It stays
  valid through the close of bar m+12 (12 bars after the MSS bar closes).
- Cancel conditions are monitored from the MSS-bar close: price trades ≥ 1 tick beyond Lf
  (no retrace) or ≥ 1 tick beyond the sweep extreme before fill. If either happens during
  bar m+1 (before arming), the setup is cancelled. A touch of the entry during bar m+1 does
  not count as a fill; the order must fill after arming.
- Stop = sweep extreme ± 3 pts.

### Model D — Order Block
- BOS (bearish): a bearish displacement bar d whose close < the most recent swing low that
  was confirmed by the close of bar d−1, provided no bar closed below that swing low between
  its confirmation and d−1 (the first break only). No sweep is required. Bullish mirrored.
- Bearish OB = the LAST bar with close > open among bars d−5..d−1. If none, there is no setup.
  Zone = [low, high] of that bar. Bullish OB mirrored (last close < open bar).
- Limit at the zone midpoint, armed at the close of d, valid for 24 5m bars (through the close
  of d+24), never past the window end.
- Cancel if a 5m bar CLOSES beyond the zone's far edge (above the high for a bearish OB)
  before fill. The cancel takes effect at that 5m close, so a 1m fill earlier in that 5m bar
  stands.
- Stop = far edge ± 3 pts. Model D uses no PDH/PDL/ONH/ONL levels.

## 5. Windows (CT)

| Window | Time (CT) | Levels | Models |
|---|---|---|---|
| NY-AM | 08:30–11:00 | PDH, PDL, ONH, ONL | A, B, D |
| SB-AM | 09:00–10:00 | PDH, PDL, ONH, ONL | A |
| SB-PM | 13:00–14:00 | PDH, PDL, ONH, ONL | A |
| ASIA | 17:00–20:00 | PDH, PDL | A, B, D |

- Interpretation (stricter than "armed and filled in window"): every signal bar (sweep bar s,
  MSS/displacement bar, bar3) must have its open time ≥ window start, the arm time must be
  ≤ window end, and the fill time must be < window end. A pending order is cancelled at the
  window end.
- The day key is the CT calendar date of the window start (the ASIA window on Sunday evening
  belongs to that Sunday date).

## 6. Execution (simulated on 1m bars)

- **Limit fill**: a sell limit at P fills only if a 1m bar's high ≥ P + 1 tick (a buy limit
  mirrored). Fill price = P. Only 1m bars starting at or after the arm time are eligible.
- **Target**: hit only if price trades ≥ 1 tick THROUGH the target. Fill = target.
- **Stop**: hit if price touches the stop. Fill = the worse of the stop and the 1m bar open
  (gap), plus 1 tick of slippage.
- **Same 1m bar reaches both stop and target**: the stop is assumed first.
- **Entry bar**: in the 1m bar where the limit fills, only the stop is checked. The target is
  not credited in the fill bar.
- **Exits** (pre-registered, each its own test):
  X1 = target at entry ± 2R; X2 = fixed target at entry ± 40 pts. Stops are per model.
- **Time exits** (market at the close of the last allowed 1m bar, with 1 tick of slippage):
  NY-AM/SB-AM/SB-PM: flat at 14:55 CT (close of the 14:54 1m bar).
  ASIA: flat at the earlier of fill + 3h or 23:00 CT. No trade ever holds through the 16:00 halt.
- **Costs**: $1.00 round-trip commission per trade plus the slippage above. Zero-cost results
  (no commission, no slippage) are also reported.
- **Constraints, within each test independently**: one position at a time; one pending order
  at a time (signals that occur while an order is pending or a position is open are ignored,
  not queued); after 2 losing trades (net $ < 0) in a window on a day, no new orders in that
  window on that day.

## 7. Tests (40 total, all in the multiple-testing family)

1. **Primary (16)**: A × {NY-AM, SB-AM, SB-PM, ASIA} × {X1, X2} = 8;
   B × {NY-AM, ASIA} × {X1, X2} = 4; D × {NY-AM, ASIA} × {X1, X2} = 4. Long and short pooled.
   H1: mean net $ per trade > 0. p = one-sided one-sample t-test.
2. **1H-bias (16)**: the same 16 configurations, with the bias filter applied at the signal
  stage (only signals whose direction equals the 1H bias at arm time; neutral is excluded),
  then re-simulated so the occupancy and loss-limit rules apply to the filtered strategy.
   Same H1 and test.
3. **Confluence (8)**: Model A, 4 windows × 2 exits, from the primary trade lists. Group
   "in" = trades whose FVG midpoint retracement r ∈ [0.62, 0.79], where (short)
   r = (mid − Lf) / (H − Lf) with the leg defined as in Model B (no 20-pt minimum).
   Statistic = mean net $ (in) − mean net $ (out). p = two-sided permutation test,
   10,000 label permutations. If either group is empty, p = 1 and the test is reported as
   "not computable".

**Descriptive splits (not tests, never used for selection):** long/short, level type, year,
month, weekday, 30-minute bucket of the fill, prior-day RTH range tercile (terciles over the
full sample), and funnel counts (signals → stale/skip → armed → cancelled/expired → filled →
excluded for roll).

## 8. Controls (for each of the 32 standalone tests)

- **Random-direction null**: 1000 simulations. Each simulation has as many trades as the real
  test. For each real trade, draw a trading date uniformly from the test's dates and a 5m bar
  open uniformly within the same window and the same 30-minute bucket as the real fill. Enter
  at that bar's open price with no slippage and a random direction (p = 0.5). Draw the stop
  distance uniformly with replacement from the real trades' R values. Apply the same exit rule
  (X1 = 2R, X2 = 40 pts), time exits, slippage and costs. Statistic = mean net $ per trade.
  Report the real result's percentile (the share of null means < the real mean). Real
  directions are never copied.
- **Mirror control**: each real trade is re-simulated from the same fill time and price in the
  opposite direction with the same stop and target distances and the same rules. Report the
  real vs the mirrored expectancy.
- Confluence tests have no null or mirror (they are a within-model comparison).

## 9. Statistics

- **IS/OOS**: a single calendar cutoff = first date + 0.70 × (last date − first date) of the
  dataset; IS = trades with fill time before the cutoff, OOS = after. Both are reported.
  Nothing is tuned.
- **Per test**: trades, win rate, breakeven win rate (= avg|loss| / (avg win + avg|loss|)),
  avg win, avg loss, expectancy in $ and R, profit factor, max drawdown ($), longest losing
  streak, t-test p-value, bootstrap 95% CI of the mean (10,000 resamples, percentile).
  Reported with and without costs; all inference uses net $ with costs.
- **Multiplicity**: Holm–Bonferroni across all 40 p-values (the primary family). Also report
  Benjamini–Hochberg q-values and the expected number of false positives at p < 0.05
  (= 0.05 × 40 = 2.0).
- **Candidate edge** (32 standalone tests) requires ALL of:
  1. net expectancy > 0 in BOTH IS and OOS;
  2. ≥ 200 trades in total (otherwise labeled "underpowered", never a candidate);
  3. net P&L > 0 in ≥ 4 calendar years;
  4. real mean > the 95th percentile of the random-direction null;
  5. real expectancy > mirrored expectancy;
  6. Holm-corrected p < 0.10.
  Otherwise the verdict is: **"no evidence of an edge."**
- **Monte Carlo** (per standalone test with ≥ 1 trade): 2000 random orderings of the trade
  P&Ls, each a fresh account starting at $0. Drawdown = max peak-to-trough with the start
  counting as a peak. Report P(DD > $292 within the first 50 trades) and P(DD > $500 within
  the first 100 trades). If a test has fewer trades than the horizon, sample with replacement
  up to the horizon and flag it.
- Seeds: base seed 20261026; each test and control derives its seed deterministically from
  the base seed and the test id.

## 10. Validation before results are produced

1. An independent brute-force 1m simulator (separate code, written loop-by-loop from §6)
   is compared with the main engine on 500 randomly sampled trades (fixed seed). It must give
   0 mismatches in fill time/price, exit time/price/reason and net $. Otherwise the run halts.
2. Automated look-ahead checks: every level, swing, FVG, ATR and bias value is asserted to be
   known (known-time ≤ use-time) for all signals. 100 random signals per model are re-verified
   rule-by-rule with independent hand-coded assertions.
3. Visual check: 15 random trades per model (fixed seed) are saved as annotated PNGs in
   `backtest_ict/charts_check/` showing candles, the level, the sweep bar, the MSS/BOS bar, the
   FVG/OTE/OB zone, entry, stop, target and exit.

## 11. Interpretation log (ambiguous ICT terms → chosen operational definition)

| # | Term / ambiguity | Chosen definition |
|---|---|---|
| 1 | "Previous regular session" | Most recent completed 08:30–15:00 CT RTH session (§2). |
| 2 | ONH/ONL boundaries | Open times in [17:00 prev, 08:30); usable from 08:30. |
| 3 | Sweep vs breakout from the other side | Requires close[s−1] on the near side of the level. |
| 4 | Several levels swept by one bar | One sweep, labeled by priority PDH>ONH / PDL>ONL. |
| 5 | Swing ties | Strict inequality; ties are not swings. |
| 6 | "Most recent swing formed before the sweep" | Pivot < s and confirmed by the close of m−1. |
| 7 | "Within 12 bars after the sweep" | m ∈ [s+1, s+12] and m ≥ reclaim bar; first qualifying bar. |
| 8 | Displacement "body ≥ 1 ATR" | Body in the signal direction; ATR as of the prior bar close. |
| 9 | ATR smoothing | Wilder (RMA), period 14. |
| 10 | FVG "centered on MSS bar" | bar1 = m−1, bar3 = m+1; gap ≥ 2.0 pts inclusive; no other FVG searched. |
| 11 | Arming time of Model B (needs FVG) | Armed at the m+1 close; expires at the m+12 close. |
| 12 | B pre-arm events in bar m+1 | Cancel if invalidated; touches of the entry are not fills. |
| 13 | Fill and cancel in the same 1m bar (A, B) | Fill assumed first (conservative). |
| 14 | BOS "most recent swing" | Swing confirmed by d−1, and its first close-break only. |
| 15 | OB candle | Last opposite-color bar in d−5..d−1; doji (close = open) is not counted. |
| 16 | "Armed and filled inside window" | All signal bars inside the window too; pending orders die at the window end. |
| 17 | Marketable limit at arm time | Skipped as "stale". |
| 18 | Tick rounding of entries and targets | Toward the less favorable price / toward the entry. |
| 19 | Entry-bar ambiguity | Stop is checked in the fill bar; target is not. |
| 20 | Time-exit price | Close of the last allowed 1m bar ± 1 tick of slippage. |
| 21 | "Losing trade" for the 2-loss cap | Net $ < 0 after costs. |
| 22 | Bias filter in tests 17–32 | Applied at the signal stage and re-simulated (not a post-hoc filter). |
| 23 | Confluence leg | Same as Model B's leg, without the 20-pt minimum. |
| 24 | Null "same window and 30-minute buckets" | Matched per real trade on the bucket of the fill time, random date. |
| 25 | IS/OOS split basis | Calendar-time cutoff at 70% of the data span, shared by all tests. |
| 26 | One-sided vs two-sided | One-sided t-test (mean > 0) for the standalone tests; two-sided permutation for confluence. |
| 27 | Roll-date-only logs | The whole CT date is treated as the roll period. |
| 28 | MC with fewer trades than the horizon | Sample with replacement to the horizon; flagged. |
