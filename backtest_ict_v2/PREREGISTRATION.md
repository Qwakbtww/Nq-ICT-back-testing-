# MNQ ICT study v2 ("ICT v2"): PRE-REGISTRATION

Status: FROZEN. The SHA-256 of this file is stored in `PREREGISTRATION.sha256`. The main script
recomputes it and refuses to run on a mismatch. No variant, parameter or test may be added after
results are seen. Bugs found later go in numbered `AMENDMENT_NNN.md` files (reason, change, rerun,
and both the original and amended results). Anything not listed here is reported only in a section
labeled **"exploratory, not evidence"**.

Written 2026-10-26, before any v2 code was written. No P&L, win rate or expectancy figure of any
kind is printed (smoke runs included) until the validation suite (§10) has passed. Signal and fill
COUNTS may be printed.

## 0. Honesty clause (verbatim; also in the README)

v2 was designed AFTER seeing study-2 results on this same data. Therefore ANY positive v2 result on this history is NOT out-of-sample evidence; it is at most a lead. The only real confirmation is the forward test (see deliverables): frozen rules run on data after 2026-10-23.

Additional disclosure: the analyst who writes this file also produced and saw the earlier ICT study
(`backtest_ict/`) on the same data. The design fixes below respond to flaws found there.

Scope: this tests ONE rigid, mechanical interpretation of each model. It says nothing about how a
skilled discretionary trader applies ICT. The default conclusion is **"no evidence of an edge"**.

## 1. Data (reused; no new download)

- Back-adjusted MNQ 1m series `backtest_ict/data/mnq_1m_adj.parquet` and `backtest_ict/data/roll_log.csv`,
  built by `backtest_ict/build_data.py` (volume-based rolls at the 17:00 CT session open; additive
  back-adjustment). Span 2019-05-05 22:03 UTC to 2026-10-23 20:59 UTC.
- The data layer and engine primitives are imported from `backtest_ict/ict_core.py` (bars,
  resampling, levels, swings, displacement, 1H bias, 1m exit simulator, exit cutoff). No earlier
  results file is read.
- Timestamps are explicit `datetime64[ns, UTC]` (asserted), converted to America/Chicago with the
  tz database (DST). Bars are labeled by open time and known only at close. No bar spans the
  16:00–17:00 CT halt.
- MNQ: tick 0.25 pt; $2.00 per point; 1 contract.
- **Roll exclusion:** a trade is excluded if a roll timestamp lies in [arm time, exit time]. The count
  is reported.

## 2. Levels and indicators (all known before use)

- **PDH/PDL** = high/low of 5m bars with open time in [08:30, 15:00) CT on the most recent date whose
  15:00 CT is ≤ the bar's open time.
- **ONH/ONL** = high/low of the bars of the current session with open time before 08:30 CT on the RTH
  date (the session starts 17:00 CT the prior evening). Usable from the 08:30 bar.
- **1H bias** = EMA 9/21/50 (`ewm(span, adjust=False)`) of 1H closes, using only 1H bars with close
  ≤ arm time. Bullish if 9>21>50, bearish if 9<21<50, else neutral. The first 50 1H bars are neutral
  (warm-up).
- **ATR** = Wilder ATR(14) on 5m bars (`ewm(alpha=1/14, adjust=False)` of true range).
  - *Displacement* uses ATR as of the close of the bar before the displacement bar.
  - *Setup ATR* (`ATR_s`) = ATR as of the close of the bar on which the order is armed. It is frozen
    for that setup and used for the stop buffer, the risk filter and the B leg minimum.

## 3. Operational definitions (5m bars)

- **Swing high at p**: high[p] strictly > the highs of the 3 bars before and the 3 bars after. Usable
  from the close of p+3. Swing low mirrored.
- **Sweep of a high level L at bar s** (low levels mirrored):
  (a) close[s−1] < L; (b) high[s] ≥ L + 1 tick; (c) the first bar r ∈ {s, s+1, s+2} with close < L is
  the reclaim bar (none → no sweep). Sweep extreme `ext` = max(high[s..r]).
  If one bar sweeps several same-side levels, the first in priority order is used: PDH, then ONH
  (PDL, then ONL).
- **Displacement bar d (bearish)**: close[d] < low[d−1], close[d] < open[d], and
  open[d] − close[d] ≥ 1.0 × ATR(close of d−1). Bullish mirrored.
- **MSS after a high sweep at s** (low sweeps mirrored): scan k = max(s+1, r) … s+12 in order.
  - k is the MSS bar m if it is a bearish displacement bar AND close[k] < low[p], where p = the most
    recent swing low with p < s and p+3 ≤ k−1.
  - **Swing-age rule:** if that most recent swing has p < s − 40, k does not qualify. There is no
    fallback to another swing.
  - **Sweep invalidation:** if k > r, k is not the MSS bar, and high[k] ≥ ext + 1 tick, the sweep is
    invalidated and the scan stops (no signal).
  - The first qualifying k is the MSS bar. If there is none, there is no signal.
- **Signal (sweep → MSS)** is shared by A1, A2 and B. Signals are deduplicated on (direction, MSS bar),
  keeping the earliest sweep bar. Direction: short after a high sweep, long after a low sweep.
- **FVG** (A1/A2 only): bar1 = m−1, bar3 = m+1. Known at the close of m+1.
  - Bearish: low[bar1] − high[bar3] ≥ 2.0 pts; zone [high[bar3], low[bar1]]; near edge = high[bar3];
    far edge = low[bar1].
  - Bullish: low[bar3] − high[bar1] ≥ 2.0 pts; zone [high[bar1], low[bar3]]; near edge = low[bar3];
    far edge = high[bar1].
  - No qualifying gap → no A1/A2 setup.
- **BOS (Model D, bearish)**: a bearish displacement bar d with close[d] < low[p], where p = the most
  recent swing low with p+3 ≤ d−1, and no bar in p+4 … d−1 closed below low[p] (first close-break
  only). No sweep is required. Bullish mirrored.
- **Order block (D)**: the last bar in d−5 … d−1 with the opposite colour (bullish candle close>open
  for a bearish BOS; bearish candle for a bullish BOS; close = open does not count). Zone = [low, high]
  of that bar. Far edge = high (bearish OB) or low (bullish OB). None → no setup.

## 4. Models

Common rules:
- **Stop buffer** = 0.1 × ATR_s beyond the structure point. The stop is rounded OUTWARD to the tick
  grid (away from the entry).
- **Risk filter**: R = |entry − stop|. Skip if R < 0.4 × ATR_s ("skip_small") or R > 3.0 × ATR_s
  ("skip_large").
- **Limit price rounding**: nearest tick; exact ties go to the less favorable side (sell → down,
  buy → up).
- **Stale**: for limit models, if the close of the arm bar is at or through the limit price (short:
  close ≥ limit; long: close ≤ limit), the setup is skipped as "stale".

| Model | Signal | Arm time | Entry | Order valid until | Cancel before fill | Stop structure point |
|---|---|---|---|---|---|---|
| A1 | sweep → MSS → FVG | close of m+1 | MARKET at the open of the first 1m bar at/after the arm time, +1 tick adverse | – | – | sweep extreme |
| A2 | sweep → MSS → FVG | close of m+1 | LIMIT at the FVG near edge | close of m+12 | price trades ≥ 1 tick beyond the sweep extreme | sweep extreme |
| B | sweep → MSS (no FVG) | close of m | LIMIT at the 70.5% retracement of the leg | close of m+24 | price trades ≥ 1 tick beyond the sweep extreme (no "no-retrace" cancel) | sweep extreme |
| D | BOS + OB | close of d | LIMIT at the OB midpoint | close of d+24 | a 5m bar CLOSES beyond the far edge | OB far edge |

- **A1 details**: ATR_s = ATR at the close of m+1. R is measured from the actual fill price (with
  slippage) to the stop, and the risk filter is applied at the fill. If the fill price is already at or
  beyond the stop (gap), the setup is skipped ("gap_through_stop"). If the entry bar's open is ≥ the
  window end, it is skipped ("fill_outside_window").
- **B leg (short case)**: H = ext; Lf = min(low[s..m]); require H − Lf ≥ 1.5 × ATR_s (ATR_s at the
  close of m), else "skip_leg". Entry = Lf + 0.705 × (H − Lf). Long mirrored: Hf = max(high[s..m]),
  entry = Hf − 0.705 × (Hf − L).
- **Cancel timing**: a price cancel is checked on 1m bars after arming. If the same 1m bar reaches both
  the fill and the cancel price, the FILL is assumed first. The D close-cancel takes effect at that 5m
  bar's close, so an earlier 1m fill inside that 5m bar stands.
- The A2, B and D cancel rules can mostly trigger only across price gaps, because price must pass the
  limit first. This is reported, not changed.

## 5. Windows (CT)

| Window | Time | Levels (A1, A2, B) | Role |
|---|---|---|---|
| NY-AM | 08:30–11:00 | PDH, PDL, ONH, ONL | tested |
| ASIA | 17:00–20:00 | PDH, PDL | tested |
| SB-PM | 13:00–14:00 | PDH, PDL, ONH, ONL | descriptive-only simulation (never a test) |

- The sweep bar (or BOS bar) open must be ≥ the window start, the arm time ≤ the window end, and the
  fill (the 1m bar's open) < the window end. Pending orders expire at the window end.
- SB-AM (09:00–10:00) is a descriptive slice of NY-AM trades by fill time.
- Day key = CT calendar date of the window.

## 6. Execution (1m bars)

- **Limit fill**: sell at P only if a 1m bar's high ≥ P + 1 tick (buy mirrored); fill = P. Only 1m bars
  with open ≥ arm time are eligible.
- **Target**: hit only if price trades ≥ 1 tick through it; fill = target. Target = entry ± k × R,
  rounded to the tick toward the entry.
  X1: k = 1.5. X2: k = 3.0.
- **Stop**: hit on touch. Fill = the worse of the stop and the 1m open (gap), ± 1 tick slippage. In the
  fill bar the fill is the stop ± 1 tick (no gap rule), and ONLY the stop is checked.
- **Stop and target in the same 1m bar**: the stop is assumed first.
- **Time exits** (close of the last allowed 1m bar ∓ 1 tick):
  - NY-AM/SB-PM: the last 1m bar with open < 14:55 CT in the fill's session.
  - ASIA: the last 1m bar with open < min(fill + 3h, 23:00 CT) in the fill's session.
  - No position crosses the 16:00 CT halt.
- **Costs**: $1.00 round-trip commission plus the slippage above. Zero-cost results (no commission, no
  slippage on stop/time exits or A1 entries) are also reported.
- **Per-test constraints**: one position and one pending order at a time. Signals arriving while busy
  are ignored, not queued. After 2 losing trades (net $ < 0) in a window on a day, no new orders that
  day in that window.
- **R accounting**: net R = net $ / (R_pts × $2). Gross-zero-cost R uses the same denominator.

## 7. Tests (32)

1. **Primary (16)**: {A1, A2, B, D} × {NY-AM, ASIA} × {X1, X2}; long and short pooled.
2. **Bias (16)**: the same 16 with the bias filter applied at the signal stage (only setups whose
   direction equals a non-neutral 1H bias at the arm time), then re-simulated.

Primary metric: **mean net R per trade**. H1: mean net R > 0; p = one-sided one-sample t-test.

**Descriptive splits (not tests, never for selection)**: long/short, level type, year, month, weekday,
30-minute bucket, SB-AM fill slice, SB-PM descriptive run, prior-day RTH range tercile, stop distance
in points by year, skip reasons by year, and an "account-fit" subset (R_pts ≤ 30).

## 8. Controls (each of the 32 tests)

- **Random-direction null**: 1000 simulations, each with as many trades as the real test.
  - For each real trade: draw a date uniformly from the window's dates and a 5m bar uniformly from the
    bars inside the window in the real fill's 30-minute bucket (redraw the date if that bucket has no
    bar).
  - Enter at that 5m bar's open (+1 tick adverse for A1 tests, none for limit models), in a uniformly
    random direction.
  - Stop distance = m × ATR (ATR at the close of the bar before entry), with m drawn with replacement
    from the real trades' R_pts / ATR_s, rounded outward to the tick (minimum 1 tick).
  - Same exit rule (1.5R / 3R), time exits, slippage and costs.
  - Statistic = mean net R. Report the real result's percentile (the share of null means < real).
- **Mirror**: each real trade re-simulated from the same fill bar and price in the opposite direction,
  with the same stop and target distances and rules. Report the real vs the mirror mean net R.

## 9. Statistics

- **IS/OOS**: one calendar cutoff = first timestamp + 0.70 × span (≈ 2024-07-27 UTC), shared by all
  tests. Also 3 consecutive blocks with equal trade counts (the last block takes the remainder).
- **Per test**: trades; win rate; breakeven win rate = |avg loss R| / (avg win R + |avg loss R|);
  avg win/loss in R and $; expectancy in R and $; profit factor ($); max drawdown ($); longest
  losing streak; one-sided t-test p (on net R); bootstrap 95% CI of the mean net R (10,000 resamples);
  **MDE** = (1.6449 + 0.8416) × SD(net R) / √n, the minimum detectable mean R at 80% power with a
  one-sided α = 0.05 (normal approximation). Zero-cost expectancy R is also reported.
- **Multiplicity**: Holm–Bonferroni and Benjamini–Hochberg across the 32 p-values. Expected false
  positives at p < 0.05 = 1.6.
- **Candidate edge** requires ALL of:
  1. mean net R > 0 in IS AND in OOS;
  2. n ≥ 200 (otherwise "underpowered");
  3. net R sum > 0 in ≥ 4 calendar years (CT year of the fill);
  4. real mean R > the 95th percentile of the null;
  5. real mean R > the mirror mean R;
  6. Holm p < 0.10.
  Otherwise: **"no evidence of an edge"**.
- **Fill-ratio flag**: tests with filled / valid setups < 30% are flagged. Valid = setups passing every
  definition, stale and risk filter.
- **Monte Carlo** (in $): 2000 random orderings per test, each a fresh account starting at $0 with the
  start counted as a peak. Report P(DD > $292 within 50 trades) and P(DD > $500 within 100 trades).
  If n < horizon, resample with replacement and flag it. Warning: risk per trade varies with stop
  size, so $ paths are not R paths.
- **Seeds**: base 20261027; each test and control derives its seed deterministically from the base
  seed and the test id.

## 10. Validation (must pass before any statistic is computed or printed)

1. An independent brute-force 1m simulator (separate code: loop-by-loop, CT times recomputed with
   pandas) vs the main engine on 500 random trades: fill bar, fill price, exit bar, exit price, exit
   reason and net $ must match exactly (0 mismatches). A **mutation test** must show that a deliberate
   1-tick change in the engine is detected.
2. Automated look-ahead assertions on every setup and trade: level known ≤ sweep bar open; swing
   confirmed ≤ the MSS/BOS bar open; FVG known at arm; ATR_s from the arm bar; 1H bias from completed
   bars; fill ≥ arm; fill < window end; swing age ≤ 40; no invalidation bar before the MSS.
3. Hand-coded rule re-verification of 100 random setups per model from independently aggregated
   5m bars and independently computed levels.
4. Truncation test: 20 setups per model re-derived from data cut at the arm time must be identical.
5. Faithfulness charts: 15 random trades per model (fixed seed) as annotated PNGs in
   `backtest_ict_v2/charts_check/`. A sample is reviewed and the result stated in the README.

## 11. Forward test

`forward_test.py` verifies this file's hash, loads any new raw Databento MNQ.FUT `ohlcv-1m` DBN files
placed in `./data_forward`, rebuilds the adjusted series with the same roll rules (existing history
prepended for warm-up), applies the frozen rules unchanged, keeps only trades with fill dates after
2026-10-23, and prints the same per-test metrics. It runs no download. The README documents a cost
check before any future download.

## 12. Numeric parameter table

| Parameter | Value |
|---|---|
| Tick / $ per point / commission | 0.25 / $2.00 / $1.00 round trip |
| Swing fractal N | 3 bars each side; confirmed at p+3 close |
| Swing max age | 40 bars before the sweep bar |
| Sweep reclaim window | 3 bars incl. the sweep bar; ≥ 1 tick through |
| MSS window | bars s+1 … s+12, ≥ reclaim bar |
| Displacement body | ≥ 1.0 × ATR(prev close) |
| FVG minimum gap | 2.0 pts |
| ATR | Wilder 14 on 5m |
| Stop buffer | 0.1 × ATR_s |
| Risk filter | 0.4 × ATR_s ≤ R ≤ 3.0 × ATR_s |
| B leg minimum / entry level | 1.5 × ATR_s / 70.5% retracement |
| Validity: A2 / B / D | to the close of m+12 / m+24 / d+24 |
| OB lookback | 5 bars |
| Exits | X1 = 1.5R, X2 = 3.0R |
| Entry slippage (A1) / stop & time exit slippage | 1 tick / 1 tick |
| Flat times | RTH 14:55 CT; ASIA min(fill+3h, 23:00 CT) |
| Loss cap | 2 losing trades per window per day |
| Null sims / bootstrap / MC | 1000 / 10,000 / 2000 |
| IS share | 70% of the calendar span |
| Candidate edge | IS>0 & OOS>0, n≥200, ≥4 positive years, >null p95, >mirror, Holm p<0.10 |
| Base seed | 20261027 |

## 13. Interpretation log (ambiguities → chosen definition)

| # | Ambiguity | Chosen definition |
|---|---|---|
| 1 | Where the data layer lives (`./data`, `./backtest`, `./backtest_levels` do not exist) | Reuse `backtest_ict/data` and `backtest_ict/ict_core.py`. |
| 2 | "ATR as of the arm-bar close" per model | A1/A2: bar m+1; B: bar m; D: bar d. Displacement still uses the prior bar's ATR. |
| 3 | Rounding of buffered stops | Outward to the tick (wider stop). |
| 4 | Rounding of R-multiple targets | Toward the entry. |
| 5 | A1 "next bar's open" | First 1m bar with open ≥ arm time; fill = open + 1 tick adverse. |
| 6 | A1 risk filter timing | Applied at the fill, with R from the actual fill price. |
| 7 | A1 open already beyond the stop | Skipped ("gap_through_stop"). |
| 8 | "Trades beyond the sweep extreme" | ≥ 1 tick beyond (high ≥ ext + tick / low ≤ ext − tick). |
| 9 | Invalidation range | Bars strictly after the reclaim bar and before the MSS bar; the MSS bar itself is exempt. |
| 10 | Swing-age rule when the most recent swing is too old | No signal for that bar; no fallback to another swing. |
| 11 | Age measured from | The sweep bar: p ≥ s − 40. |
| 12 | B leg extent | From the sweep extreme to the extreme low (high) of bars s … m inclusive. |
| 13 | B "24 bars after the MSS bar" | Through the close of bar m+24. |
| 14 | Fill and cancel in the same 1m bar | Fill first (conservative). |
| 15 | Inert cancel rules (A2, B, D) | Kept as specified; they effectively act only across gaps. Counts reported. |
| 16 | Stale check for A2 | Arm-bar (m+1) close at/through the near edge → stale. |
| 17 | Simultaneous setups | Processed by arm time, then sweep bar, then short before long. |
| 18 | Primary statistic | Net R; the null, mirror, IS/OOS, year counts and t-test all use net R. Dollar metrics are reported alongside. |
| 19 | MDE | Normal approximation: (z0.95 + z0.80) × SD / √n. |
| 20 | Null stop sizing | ATR multiple of the real trade × ATR at the close of the bar before the null entry. |
| 21 | Null entry slippage | +1 tick for A1 tests (matching market entries); none for limit models. |
| 22 | Equal-trade-count blocks | 3 chronological blocks of ⌊n/3⌋ trades; the remainder goes to the last block. |
| 23 | SB-PM split | No tested window covers 13:00–14:00, so it is a separate descriptive-only simulation. |
| 24 | "Valid signals" for the 30% flag | Setups with status ok (passed definition, stale and risk filters). |
| 25 | Calendar year for "positive years" | CT year of the fill; net R sum > 0. |
| 26 | Holiday early closes | Time exit = last 1m bar before the cutoff in the fill's session. |
| 27 | Losing trade for the loss cap | Net $ < 0 after costs. |
| 28 | Roll-excluded trades | Still occupy the slot and count toward the loss cap; removed from the statistics only. |
