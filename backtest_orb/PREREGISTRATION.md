# MNQ Opening Range Breakout (Study 4): PRE-REGISTRATION

Status: FROZEN. The SHA-256 of this file is stored in `PREREGISTRATION.sha256`. The main script
recomputes it and refuses to run on a mismatch. No variant, parameter or test may be added after
results are seen. Bugs found later go in numbered `AMENDMENT_NNN.md` files with the reason; the study
is rerun and both the original and amended results are reported. Anything not listed here is
reported only under **"exploratory, not evidence"**.

Written 2026-10-26, before any ORB code was written and before any ORB result was computed or seen.
No P&L, win rate or expectancy figure is printed anywhere (smoke runs included) until the validation
suite (§9) passes. Counts may be printed.

## 0. Honesty clause (verbatim; also in the README)

ORB is a standard, widely known idea, specified here before looking at any ORB result. But this is the 4th study on the same 2019-2026 history (~100+ tests so far across studies), so the effective multiple-testing burden is larger than this study's own 24 tests. Any positive result is a lead, not proof; the forward test is the only real confirmation. A negative result does not rule out discretionary skill.

Disclosure: the analyst has seen the results of the three earlier ICT studies on this data, but no
ORB result.

## 1. Data

- Back-adjusted MNQ 1m series `backtest_ict/data/mnq_1m_adj.parquet` and `backtest_ict/data/roll_log.csv`
  (Databento GLBX.MDP3 ohlcv-1m, MNQ.FUT; volume-based rolls at the 17:00 CT session open;
  additive back-adjustment; 2019-05-05 → 2026-10-23). The data layer is reused from
  `backtest_ict/ict_core.py` (`load_1m`, `Bars`, `resample`, `ct_time_ns`, `exit_cutoff`) and the
  tick-rounding helpers from `backtest_ict_v2/core_v2.py`. No download.
- Timestamps are explicit `datetime64[ns, UTC]` (asserted), converted to America/Chicago with the tz
  database (DST). Bars are labeled by open time; a bar is known at open + length. Nothing is held
  through the 16:00–17:00 CT halt.
- Tick 0.25; $2.00 per point; 1 contract; $1.00 round-trip commission.
- Every entry, stop and target price lies on the 0.25 grid. Stops are rounded outward (wider);
  targets toward the entry.
- **Roll exclusion:** a trade is excluded if a roll timestamp lies in [OR end, exit]. The count is
  reported (rolls occur at 17:00 CT, so RTH trades are not expected to span one).

## 2. Days and the opening range

- **Candidate days:** CT calendar dates with a 1m bar opening at exactly 08:30 CT.
- **Opening range (OR)** for N ∈ {5, 15, 30} minutes: high/low of the 1m bars with open time in
  [08:30, 08:30 + N) CT. The OR is complete only if all N 1m bars exist; otherwise the day is skipped
  for that N ("missing_or_bars", counted). The OR is known at **OR end** = 08:30 + N.
- **Trigger window:** 1m bars with open time in [OR end, 14:00:00 CT). A bar opening at or after
  14:00 cannot trigger. Pending orders expire at 14:00:00 CT, or at the session's last bar if it
  closes earlier (holiday sessions). One trade per day at most; no re-entry; the two stop orders are
  one-cancels-the-other.

## 3. Entry

- Trigger levels: T_long = OR high + 1 tick; T_short = OR low − 1 tick.
- A long triggers on the first eligible 1m bar with high ≥ T_long + 1 tick (short: low ≤ T_short − 1 tick).
- Fill price: long = max(T_long, bar open) + 1 tick; short = min(T_short, bar open) − 1 tick.
  The bar open applies when it gapped through.
- **Both-sides conflict (day-level, per N):** find the first eligible 1m bar that triggers either side.
  If that same bar triggers both sides, the day is flagged "conflict" and skipped for every variant of
  that N, before any entry simulation, filter or risk check. Counted.

## 4. Stops, risk and exits

- **S1** = the opposite OR extreme: long stop = OR low; short stop = OR high.
- **S2** = the OR midpoint (OR high + OR low) / 2, rounded outward: long → down to the tick;
  short → up to the tick.
- **Planned R** (per side) = |planned fill − stop| with planned fill = T_long + 1 tick
  (T_short − 1 tick). If planned R < 8 pts, that side's order is not placed ("skip_R<8", counted by
  year). There is no upper cap.
- **Actual R** = |actual fill − stop|; all R-multiples use the actual R.
- **Stop execution**: hit when a 1m bar touches it (long: low ≤ stop). Fill = stop − 1 tick (long);
  after the fill bar, if the bar opens beyond the stop, fill = open − 1 tick (short mirrored).
- **E1**: limit target at entry ± 2 × actual R, rounded toward the entry; hit only if price trades
  ≥ 1 tick through it.
- **E2**: no target.
- **Time exit (E1 and E2)**: at the close of the last 1m bar with open < 14:55 CT in the fill's
  session, with 1 tick slippage against the position.
- If stop and target are both reachable in the same 1m bar, the stop is assumed first. In the fill
  bar only the stop is checked.
- **Costs**: net $ = points × $2 − $1.00. Zero-cost results (no commission; no slippage on the
  entry, stop or time exit) are also reported. Net R = net $ / (actual R × $2).

## 5. Filter

- **F0**: no filter (both stop orders placed).
- **F1**: EMA(200) of 5m closes, computed with `ewm(span=200, adjust=False)` on the continuous series
  of real 5m bars (resampled from the adjusted 1m bars; no synthetic bars for the halt or weekends).
  The first 200 5m bars of the series are warm-up (no F1 trades). Value and comparison price are
  locked at the close of the last 5m bar inside the OR window:
  - N = 5: the 08:30–08:35 bar;
  - N = 15: the 08:40–08:45 bar;
  - N = 30: the 08:55–09:00 bar.

  If that bar's close is above the EMA, only the long order is placed; if below, only the short; if
  equal, none.

## 6. Tests (24)

N {5, 15, 30} × stop {S1, S2} × exit {E1, E2} × filter {F0, F1}; long and short pooled.
Primary metric: **mean net R per trade**. H1: mean > 0; p = one-sided one-sample t-test on net R.

**Descriptive splits (never for selection):** long/short, year, month, weekday, OR width tercile
(OR width / ATR(14) on 5m as of the last OR 5m bar; terciles per N over all eligible days), gap size
tercile (08:30 open − previous RTH session's last close before 15:00), "account-fit" subset
(R ≤ 30 pts), R distribution in points by year, and the share of trades with R > 30 pts.

## 7. Controls

- **Mirror**: each real trade re-simulated from the same fill bar and fill price in the opposite
  direction, with the same R and the same exit rule. Report the real vs the mirror mean net R.
- **Drift-matched random-timing null** (1000 simulations per test, same trade count). For real
  trade j on date d_j:
  - choose a uniformly random 1m bar on d_j with open in [OR end, 14:00) CT;
  - enter at its open + 1 tick adverse;
  - draw the direction as long with probability equal to the share of long real trades in d_j's
    calendar year (for that test);
  - stop distance = the real trade's actual R; target 2R for E1, none for E2;
  - same time exit, slippage and costs.
  Statistic = mean net R. Report the real mean's percentile (the share of null means < real).
- **Drift baseline (reference only)**: for each date on which the test traded, enter at the open of
  the 08:35 CT 1m bar + 1 tick adverse, always long and (separately) always short, with that day's real
  R and the test's exit rule. Report both mean net R values.

## 8. Statistics

- **IS/OOS**: one calendar cutoff = first timestamp + 0.70 × span of the data (≈ 2024-07-27 UTC),
  shared by all tests; also 3 consecutive blocks with equal trade counts (the remainder goes to the
  last block). Nothing is tuned.
- **Per test**: trades; % of eligible days traded (eligible = complete-OR, non-conflict days for that
  N); win rate; breakeven win rate = |avg loss R| / (avg win R + |avg loss R|); avg win/loss in R and
  $; expectancy in R and $; zero-cost expectancy in R; profit factor ($); max drawdown ($ and R);
  longest losing streak; one-sided t-test p; bootstrap 95% CI of the mean R (10,000 resamples);
  **MDE** = (1.6449 + 0.8416) × SD(net R) / √n.
- **Multiplicity**: Holm–Bonferroni and Benjamini–Hochberg across the 24 p-values; expected false
  positives at p < 0.05 = 1.2.
- **Candidate edge** requires ALL of:
  1. mean net R > 0 in IS and in OOS;
  2. n ≥ 200;
  3. net R sum > 0 in ≥ 4 calendar years (CT year of the fill);
  4. real mean > the 95th percentile of the drift-matched null;
  5. real mean > the mirror mean;
  6. Holm p < 0.10.
  Otherwise: **"no evidence of an edge"**.
- **Monte Carlo** ($): 2000 random orderings per test, fresh account at $0 (the start counts as a
  peak). Report P(DD > $292 within 50 trades) and P(DD > $500 within 100 trades); resample with
  replacement if n < horizon (flagged). Warning: risk per trade varies with OR width.
- **Risk budget**: the share of trades with R × $2 ≤ $50 (R ≤ 25 pts) and ≤ $62 (R ≤ 31 pts).
- **Seeds**: base 20261028; each test and control derives its seed from the base seed and the test id.

## 9. Validation (must pass before any statistic is computed or printed)

1. Independent brute-force 1m simulator (plain loops, CT times recomputed with pandas) vs the main
   engine on 500 random trades: trigger bar, fill price, stop, target, exit bar, exit price, reason and
   net $ must match exactly. A mutation test (a 1-tick change in the engine output) must be detected.
2. Automated look-ahead assertions on every trade: OR end ≤ fill bar open; EMA lock time = OR end and
   EMA bar close ≤ OR end; fill bar open < 14:00; exit ≤ 14:55 cutoff; all prices on the tick grid;
   conflict days absent.
3. Hand-coded rule re-verification of 100 random (day, N) cases from raw 1m data with independent
   code (OR, EMA, conflict, trigger, fill, stop, R filter, filter decision, target).
4. Truncation test on 20 days: OR, EMA lock and the filter decision recomputed from data cut at the
   OR end; the trigger bar and fill recomputed from data cut at the fill bar's close; both must be
   identical.
5. Faithfulness charts: 30 random trading days (fixed seed) as annotated PNGs in
   `backtest_orb/charts_check/` (OR box, trigger levels, entry, stop, target, exit). A sample is
   reviewed and the result stated in the README.

## 10. Forward test

`forward_test.py` verifies this hash, loads new raw Databento MNQ.FUT ohlcv-1m DBN files from
`./data_forward`, rebuilds the adjusted series with the same roll rule (history prepended for the
EMA warm-up), runs the 24 tests unchanged and scores only dates after 2026-10-23. Data is fetched
with a cost check and a dollar cap (`backtest_ict_v2/fetch_forward.py`); nothing is downloaded now.

## 11. Numeric parameter table

| Parameter | Value |
|---|---|
| OR lengths N | 5, 15, 30 minutes from 08:30 CT |
| Trigger | OR high + 1 tick / OR low − 1 tick; fill needs ≥ 1 tick through the trigger |
| Entry slippage | 1 tick (from the trigger, or from the open if gapped) |
| Trigger window end | 14:00:00 CT (bars opening ≥ 14:00 cannot trigger) |
| Stops | S1 opposite OR extreme; S2 OR midpoint, rounded outward |
| Minimum planned R | 8 pts (no cap) |
| Exits | E1 2R target; E2 none; time exit at the last 1m bar before 14:55 CT |
| Stop / time-exit slippage | 1 tick |
| Filter | F1 = EMA(200) on 5m closes, locked at the last OR 5m bar close |
| Costs | $2/pt, $1.00 round trip |
| Null sims / bootstrap / MC | 1000 / 10,000 / 2000 |
| IS share | 70% of the calendar span |
| Candidate edge | IS>0 & OOS>0, n≥200, ≥4 positive years, >null p95, >mirror, Holm p<0.10 |
| Base seed | 20261028 |

## 12. Interpretation log (ambiguities → chosen definition)

| # | Ambiguity | Chosen definition |
|---|---|---|
| 1 | "Fills when a 1m bar trades ≥ 1 tick through" | Through the trigger level: high ≥ T_long + 1 tick (low ≤ T_short − 1 tick). |
| 2 | Fill price | max(T_long, open) + 1 tick (short: min(T_short, open) − 1 tick). |
| 3 | Scope of the both-sides conflict | Day-level per N: if the first bar triggering either side triggers both, skip all 8 variants of that N that day. |
| 4 | Conflict test with F1 (one order) | Same day-level flag; F1 skips the same conflict days (identical day sets across variants). |
| 5 | F1 order placement | Only the allowed side's order is placed; it may trigger after the other side was touched. |
| 6 | EMA equality | No trade. |
| 7 | EMA warm-up | The first 200 5m bars of the series; no F1 trades before that. |
| 8 | R < 8 check timing | At order placement, with the planned fill (trigger ± 1 tick); actual R is used for P&L. |
| 9 | S1 stop placement | Exactly at the opposite OR extreme (on tick); hit on touch. |
| 10 | Time-exit slippage | 1 tick, consistent with the earlier studies. |
| 11 | Complete OR | All N 1m bars present in [08:30, 08:30+N). |
| 12 | Holiday / early-close sessions | Traded if the OR is complete; orders expire at the last available bar before 14:00; time exit at the last bar before 14:55 in the session. |
| 13 | Null "same dates" | Each null trade uses the date of a real trade (one-to-one) and that trade's R. |
| 14 | Null entry price | Bar open + 1 tick adverse (like a market/stop fill). |
| 15 | Null direction proportions | Long probability = the long share of the real trades in that calendar year, for that test. |
| 16 | Drift baseline R and dates | The test's traded dates and their real R; entry at the 08:35 1m open + 1 tick. |
| 17 | Gap size | 08:30 open − last close of the previous RTH session (last 1m bar before 15:00 CT). |
| 18 | OR width normaliser | ATR(14) Wilder on 5m at the close of the last OR 5m bar. |
| 19 | Risk-budget fraction | R × $2 ≤ $50 and ≤ $62 (excluding commission and slippage). |
| 20 | Calendar year for "positive years" | CT year of the fill; net R sum > 0. |
