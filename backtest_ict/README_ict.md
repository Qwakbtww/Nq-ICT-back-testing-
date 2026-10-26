# Do ICT models have an edge on MNQ? A pre-registered, mechanical test

## Verdict

**No evidence of an edge.** None of the 32 standalone tests met the pre-registered "candidate edge" criteria. None of the 8 confluence comparisons showed a significant difference. After Holm–Bonferroni correction across all 40 tests, **every corrected p-value is 1.000**. Only one raw p-value is below 0.05 (D-ASIA-X1, p = 0.048), while chance alone would produce about 2.0 of 40.

| Model | What happened | Trades (primary tests) | Verdict |
|---|---|---|---|
| A: Sweep + FVG | Average results near zero. NY-AM expectancy is −$0.36 (X1) and +$0.97 (X2) per trade. Out-of-sample NY-AM is negative. The SB/ASIA results are positive but rest on 12–19 trades. | 63 / 12 / 12 / 19 (NY-AM / SB-AM / SB-PM / ASIA) | Underpowered everywhere; no evidence of an edge |
| B: OTE | Very few fills: 81% of signals were invalidated before the order could be armed. | 16 (NY-AM), 2 (ASIA) | Underpowered; no evidence of an edge |
| D: Order block, NY-AM | **Consistently negative:** −$4.55 per trade (X1) and −$4.29 (X2). It loses in 7 of 8 years, in both IS and OOS, sits below the median of the random-direction null, and the 95% CI is entirely below zero. | 831 / 832 | No evidence of an edge (negative) |
| D: Order block, ASIA | +$4.72 (X1) and +$3.67 (X2) per trade. It beats the random-direction null (99.8th / 97.0th percentile) and its mirror, but in-sample is slightly negative (−$0.18) and all the profit comes from 2024–2026. Holm p = 1.000. | 201 / 201 | No evidence of an edge (fails the IS and corrected-p criteria; a lead at most) |

**What this does and does not show.** This study tests **one rigid, mechanical reading** of each ICT model, pre-registered before any result was seen. It does **not** test how a skilled discretionary trader applies ICT: such a trader picks context, skips poor setups, and reads "displacement" or "market structure" more flexibly. A negative result here therefore does **not** prove that discretionary ICT trading has no skill. A positive result would only have been a lead to investigate, not proof.

## Data

- **Source:** Databento `GLBX.MDP3`, schema `ohlcv-1m`, parent symbol `MNQ.FUT` (all outright contracts; spreads dropped). Downloaded once on 2026-10-26 for **$14.68** of the account's credit (`fetch_data.py`). Everything after that runs offline. The raw file and the adjusted series are git-ignored because the repository is public and the data is under Databento's licence.
- **Span:** 2019-05-05 22:03 UTC (MNQ's first session) to 2026-10-23 20:59 UTC. This gives 2,635,600 adjusted 1m bars, 528,056 5m bars and 44,175 1H bars.
- **Continuous series** (`build_data.py`):
  - Session D trades the outright with the highest volume in session D−1, and the front never rolls back to an earlier contract.
  - That gives **30 rolls**, each at the 17:00 CT session open (`data/roll_log.csv`).
  - The adjustment is additive, back-propagated, and measured at the last common 1m bar before each roll. Additive adjustment keeps point distances, and so stops and targets, exact.
  - Every adjusted price was checked to lie on the 0.25 tick grid.
- **Time handling:**
  - Timestamps are explicit `datetime64[ns, UTC]` (asserted) and converted to `America/Chicago` with the tz database, which handles DST.
  - Bars are labelled by open time and only used once they have closed.
  - No bar spans the 16:00–17:00 CT halt.
- **Data quality:** Databento flags 19 days in the span as "degraded" (`data/degraded_days.csv`). Only 16 of the 3,215 trade rows fall on those UTC dates, all in Model D. They were kept, as the pre-registration did not say to drop them.
- **Roll exclusions:** 0. Every roll happens at the 17:00 open, while RTH trades are flat by 14:55 and ASIA orders are armed after 17:00. So no trade's arm-to-exit interval contains a roll.
- **IS/OOS cutoff:** 70% of the calendar span, at 2024-07-27 11:42 UTC.

## How to run

```bash
pip install databento pandas numpy scipy matplotlib pyarrow
# one-time download (spends Databento credit; key file path in env, never printed):
DATABENTO_KEY_FILE=/path/to/keyfile python3 backtest_ict/fetch_data.py
python3 backtest_ict/build_data.py      # adjusted 1m series + roll_log.csv
python3 backtest_ict/run_ict.py         # verifies the pre-registration hash, validates, runs everything (~7 min)
```

`run_ict.py` recomputes the SHA-256 of `PREREGISTRATION.md` and exits if it differs from `PREREGISTRATION.sha256` (`4717ae4e…578ad`). It then runs the validation suite and halts on any failure before computing statistics.

## Exact definitions

The binding definitions are in **[PREREGISTRATION.md](PREREGISTRATION.md)**, which was frozen and pushed before any test code was written. Summary:

- **Levels:**
  - PDH/PDL = high/low of the most recent completed 08:30–15:00 CT session, usable from 15:00.
  - ONH/ONL = high/low from 17:00 CT the previous evening to 08:30, usable from 08:30.
  - NY-AM, SB-AM and SB-PM use all four levels; ASIA uses PDH/PDL only.
- **1H bias:** EMA 9/21/50 stack on completed 1H bars only.
- **ATR:** ATR(14), Wilder smoothing, on 5m bars, taken as of the previous bar's close.
- **Swing:** strict 3-bar fractal, confirmed 3 bars later.
- **Sweep:**
  - the previous bar closed on the near side of the level;
  - the bar trades at least 1 tick through it;
  - a close back across the level comes within 3 bars, including the sweep bar.
  - The sweep extreme is the highest high (lowest low) from the sweep bar to the reclaim bar.
- **Displacement:** the bar closes beyond the prior bar's extreme in the signal direction, and its body is at least 1.0 × ATR.
- **MSS:** the first displacement bar within 12 bars after the sweep bar that closes beyond the most recent swing in the opposite direction formed before the sweep bar (confirmed by the previous bar's close).
- **FVG:** the gap between bar MSS−1 and bar MSS+1, at least 2.0 pts, known at the close of MSS+1.
- **Model A:** limit at the FVG midpoint, valid 12 bars. Cancelled if price trades beyond the sweep extreme. Stop = sweep extreme ± 3 pts.
- **Model B:**
  - Leg = sweep extreme to the far extreme reached up to the MSS bar, and must be at least 20 pts.
  - Limit at the 70.5% retracement, armed at the FVG confirmation and valid until 12 bars after the MSS bar.
  - Cancelled on 1 tick beyond the far end (no retrace) or beyond the sweep extreme.
  - Stop = sweep extreme ± 3 pts.
- **Model D:**
  - Break of structure = the first close beyond the most recent confirmed swing, made by a displacement bar.
  - Order block = the last opposite-coloured candle among the 5 bars before it.
  - Limit at the order block midpoint, valid 24 bars, cancelled on a 5m close beyond the far edge.
  - Stop = far edge ± 3 pts.
- **All models:** skipped if the stop distance R is under 8 pts or over 40 pts.
- **Execution, simulated on 1m bars:**
  - Limits fill only when price trades at least 1 tick through, and targets also need 1 tick through.
  - Stops fill as market orders with 1 tick of slippage, at the bar open if price gapped past the stop.
  - If stop and target are both reachable in the same 1m bar, the stop counts first. In the fill bar only the stop is checked.
  - X1 target = 2R; X2 target = 40 pts.
  - RTH trades are flat by 14:55 CT. ASIA trades are flat at fill + 3h or at 23:00 CT, whichever comes first.
  - Costs: $2 per point and $1.00 round-trip commission; results are also shown with zero costs.
  - One position and one pending order at a time; at most 2 losses per window per day.

### Interpretation log (copied from the pre-registration)

| # | Term / ambiguity | Chosen definition |
|---|---|---|
| 1 | "Previous regular session" | Most recent completed 08:30–15:00 CT RTH session. |
| 2 | ONH/ONL boundaries | Open times in [17:00 previous evening, 08:30); usable from 08:30. |
| 3 | Sweep vs. a breakout from the other side | Requires the prior bar's close on the near side of the level. |
| 4 | Several levels swept by one bar | One sweep, labelled by priority PDH > ONH / PDL > ONL. |
| 5 | Swing ties | Strict inequality; ties are not swings. |
| 6 | "Most recent swing formed before the sweep" | Pivot < sweep bar, confirmed by the close of the bar before the MSS bar. |
| 7 | "Within 12 bars after the sweep" | MSS bar in [s+1, s+12], at or after the reclaim bar; the first qualifying bar. |
| 8 | Displacement "body ≥ 1 ATR" | Body in the signal direction; ATR as of the prior bar's close. |
| 9 | ATR smoothing | Wilder (RMA), period 14. |
| 10 | FVG "centered on the MSS bar" | bar1 = MSS−1, bar3 = MSS+1; gap ≥ 2.0 pts inclusive; no other FVG searched. |
| 11 | Arming time of Model B (needs the FVG) | Armed at the MSS+1 close; expires at the MSS+12 close. |
| 12 | B events during bar MSS+1, before arming | Cancel if invalidated; touches of the entry are not fills. |
| 13 | Fill and cancel in the same 1m bar (A, B) | Fill assumed first (conservative). |
| 14 | Break of structure: "most recent swing" | Swing confirmed by the bar before the displacement bar, and only its first close-break. |
| 15 | Order-block candle | Last opposite-coloured bar among the 5 before; a doji is not counted. |
| 16 | "Armed and filled inside the window" | All signal bars inside the window too; pending orders expire at the window end. |
| 17 | Marketable limit at arm time | Skipped as "stale". |
| 18 | Tick rounding of entries and targets | Toward the less favourable price / toward the entry. |
| 19 | Entry-bar ambiguity | Stop checked in the fill bar; target not. |
| 20 | Time-exit price | Close of the last allowed 1m bar ± 1 tick of slippage. |
| 21 | "Losing trade" for the 2-loss cap | Net $ < 0 after costs. |
| 22 | Bias filter in tests 17–32 | Applied at the signal stage and re-simulated (not a post-hoc filter). |
| 23 | Confluence leg | Same as Model B's leg, without the 20-pt minimum. |
| 24 | Null "same window and 30-minute buckets" | Matched per real trade on the bucket of the fill time, random date. |
| 25 | IS/OOS split basis | Calendar-time cutoff at 70% of the data span, shared by all tests. |
| 26 | One-sided vs. two-sided | One-sided t-test (mean > 0) for standalone tests; two-sided permutation for confluence. |
| 27 | Roll logs with only dates | Whole CT date treated as the roll period (not needed: the log has timestamps). |
| 28 | Monte Carlo with fewer trades than the horizon | Sample with replacement up to the horizon; flagged. |

### Implementation details the pre-registration did not spell out

These choices were made while coding, before any validated results existed. None of them changes a parameter.

- **Simultaneous setups:** a bar that sweeps a high and a low level at once creates two candidate setups. They are processed by arm time, then sweep bar, then short before long. Duplicate signals sharing one MSS bar are merged, keeping the earliest sweep bar.
- **Holiday early closes:** "flat by 14:55" is implemented as "flat at the last 1m bar before 14:55 *in the fill's session*", so no position ever crosses a halt.
- **Gap rule for stops:** the gap fill price (the bar open) is applied from the bar after the fill bar. In the fill bar itself the stop fills at the stop price plus 1 tick.
- **Roll-excluded trades:** they would still have occupied the position slot and counted toward the loss cap. This is moot here because there were 0 such trades.
- **Disclosure:** before validation, a smoke run printed rough per-test trade counts and means to confirm the code ran end to end. No rule, parameter or variant was changed after it. `PREREGISTRATION.md` is byte-identical to the hash committed before any code existed.

## Validation (all passed before statistics were computed)

| Check | Result |
|---|---|
| Independent brute-force 1m simulator vs. main engine, 500 random trades: fill bar, exit bar, exit price, reason, net $ | **0 mismatches** |
| Mutation test of that comparison: deliberately adding 1 tick to stop/time exits in the engine | 364 / 500 mismatches detected, so the check has teeth |
| Automated look-ahead assertions on all 5,292 setups and all trades: level known before the sweep bar, swing confirmed before the MSS bar, FVG known at arm time, 1H bias from completed bars, fill after arm, fill before window end | Pass |
| Rule-by-rule hand-coded re-verification of 100 random setups per model, from independent 5m aggregation, independently computed levels, hand-rolled ATR and swing checks | Pass (300 / 300). A mutation test that corrupted levels, entries, stops, swings or order blocks was caught 40/40 for each field. |
| Truncation test: 20 setups per model re-derived from data ending at the arm time | 60 / 60 identical |
| Visual faithfulness check: 15 random trades per model (fixed seed) | `charts_check/model{A,B,D}_NN.png`, reviewed |

## Results

40 pre-registered tests: 16 primary, 16 with the 1H-bias filter, and 8 confluence comparisons.

- Expected false positives at p < 0.05 by chance: **2.0**. Observed raw p < 0.05: **1**.
- Holm–Bonferroni and Benjamini–Hochberg are both applied across all 40 tests.
- A standalone test is a "candidate edge" only if it meets **all** of the following:
  - positive in IS **and** OOS;
  - at least 200 trades;
  - positive in at least 4 calendar years;
  - above the 95th percentile of the random-direction null;
  - better than its mirror;
  - Holm p < 0.10.

Column notes:

- **Null pct:** the real expectancy's percentile within 1000 random-direction simulations, which use the same window, the same 30-minute bucket, random direction and resampled stop distances.
- **Mirror exp $:** the same fills traded in the opposite direction with the same stop and target distances.
- **Verdict "fails":** lists every criterion the test missed.

#### Results, all 32 standalone tests (net of costs; p = one-sided t-test)

| # | Test | n | IS/OOS n | Win% | BE win% | Avg win | Avg loss | Exp $ | Exp R | Exp $ 0-cost | PF | Max DD $ | Loss streak | p raw | p Holm | p BH | 95% CI $ | Exp IS | Exp OOS | Yrs + | Null pct | Mirror exp $ | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | A-NYAM-X1 | 63 | 57/6 | 41.3 | 41.5 | 80.38 | -57.09 | -0.36 | 0.033 | 1.02 | 0.99 | 518 | 7 | 0.515 | 1.000 | 1.000 | [-18.37, 18.38] | 2.95 | -31.75 | 3/7 | 55.5 | -6.39 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 2 | A-NYAM-X2 | 63 | 57/6 | 44.4 | 43.7 | 70.55 | -54.70 | 0.97 | 0.024 | 2.29 | 1.03 | 454 | 5 | 0.454 | 1.000 | 1.000 | [-14.81, 17.01] | 2.96 | -18.00 | 4/7 | 63.0 | -2.83 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,null,p_holm) |
| 3 | A-SBAM-X1 | 12 | 11/1 | 50.0 | 34.0 | 110.33 | -56.83 | 26.75 | 0.457 | 28.04 | 1.94 | 149 | 2 | 0.166 | 1.000 | 1.000 | [-22.96, 76.46] | 15.09 | 155.00 | 3/5 | 88.0 | 3.58 | underpowered; no evidence of an edge (fails: underpowered,years,null,p_holm) |
| 4 | A-SBAM-X2 | 12 | 11/1 | 50.0 | 41.8 | 79.00 | -56.83 | 11.08 | 0.222 | 12.33 | 1.39 | 149 | 2 | 0.304 | 1.000 | 1.000 | [-28.29, 48.50] | 4.91 | 79.00 | 3/5 | 74.1 | 2.54 | underpowered; no evidence of an edge (fails: underpowered,years,null,p_holm) |
| 5 | A-SBPM-X1 | 12 | 11/1 | 41.7 | 39.8 | 92.60 | -61.21 | 2.88 | 0.156 | 4.25 | 1.08 | 204 | 3 | 0.453 | 1.000 | 1.000 | [-39.88, 49.38] | -3.77 | 76.00 | 3/6 | 59.6 | -10.62 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 6 | A-SBPM-X2 | 12 | 11/1 | 50.0 | 43.2 | 79.00 | -60.00 | 9.50 | 0.288 | 10.75 | 1.32 | 136 | 2 | 0.331 | 1.000 | 1.000 | [-29.62, 46.00] | 3.18 | 79.00 | 3/6 | 77.0 | -11.17 | underpowered; no evidence of an edge (fails: underpowered,years,null,p_holm) |
| 7 | A-ASIA-X1 | 19 | 13/6 | 57.9 | 45.2 | 58.50 | -48.19 | 13.58 | 0.511 | 14.87 | 1.67 | 185 | 4 | 0.168 | 1.000 | 1.000 | [-13.00, 39.50] | 25.50 | -12.25 | 5/8 | 90.9 | -16.63 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,null,p_holm) |
| 8 | A-ASIA-X2 | 19 | 13/6 | 47.4 | 42.4 | 61.06 | -45.00 | 5.24 | 0.224 | 6.61 | 1.22 | 185 | 4 | 0.349 | 1.000 | 1.000 | [-20.50, 30.11] | 11.31 | -7.92 | 4/8 | 74.9 | -16.95 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,null,p_holm) |
| 9 | B-NYAM-X1 | 16 | 14/2 | 31.2 | 28.4 | 114.00 | -45.32 | 4.47 | -0.094 | 5.81 | 1.14 | 342 | 7 | 0.412 | 1.000 | 1.000 | [-29.91, 43.50] | -1.18 | 44.00 | 4/6 | 64.3 | -11.59 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,null,p_holm) |
| 10 | B-NYAM-X2 | 16 | 14/2 | 31.2 | 36.5 | 79.00 | -45.32 | -6.47 | -0.250 | -5.12 | 0.79 | 342 | 7 | 0.663 | 1.000 | 1.000 | [-32.88, 24.00] | -10.18 | 19.50 | 3/6 | 40.8 | -8.28 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 11 | B-ASIA-X1 | 2 | 0/2 | 50.0 | 40.3 | 60.00 | -40.50 | 9.75 | 0.464 | 11.00 | 1.48 | 40 | 1 | 0.439 | 1.000 | 1.000 | [-40.50, 60.00] | – | 9.75 | 1/2 | 58.4 | -36.25 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 12 | B-ASIA-X2 | 2 | 0/2 | 0.0 | 100.0 | 0.00 | -36.25 | -36.25 | -1.044 | -34.75 | 0.00 | 72 | 2 | 0.963 | 1.000 | 1.000 | [-40.50, -32.00] | – | -36.25 | 0/2 | 5.7 | -36.25 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,mirror,p_holm) |
| 13 | D-NYAM-X1 | 831 | 569/262 | 29.1 | 33.3 | 72.57 | -36.23 | -4.55 | -0.171 | -3.19 | 0.82 | 4258 | 16 | 0.992 | 1.000 | 1.000 | [-8.18, -0.82] | -3.05 | -7.79 | 1/8 | 12.0 | -11.00 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 14 | D-NYAM-X2 | 832 | 570/262 | 26.6 | 30.4 | 78.58 | -34.26 | -4.29 | -0.185 | -2.92 | 0.83 | 3940 | 20 | 0.992 | 1.000 | 1.000 | [-7.79, -0.77] | -4.06 | -4.77 | 1/8 | 13.1 | -11.95 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 15 | D-ASIA-X1 | 201 | 73/128 | 38.3 | 32.1 | 51.44 | -24.29 | 4.72 | 0.092 | 6.03 | 1.32 | 316 | 12 | 0.048 | 1.000 | 1.000 | [-0.71, 10.20] | -0.18 | 7.52 | 4/8 | 99.8 | -5.19 | no evidence of an edge (fails: IS/OOS,p_holm) |
| 16 | D-ASIA-X2 | 201 | 73/128 | 27.9 | 24.2 | 75.32 | -24.00 | 3.67 | 0.079 | 5.05 | 1.21 | 352 | 12 | 0.128 | 1.000 | 1.000 | [-2.38, 10.10] | -0.11 | 5.83 | 5/8 | 97.0 | -6.60 | no evidence of an edge (fails: IS/OOS,p_holm) |
| 17 | A-NYAM-X1+bias | 5 | 5/0 | 40.0 | 63.0 | 27.75 | -47.33 | -17.30 | -0.237 | -15.80 | 0.39 | 86 | 2 | 0.758 | 1.000 | 1.000 | [-56.60, 22.00] | -17.30 | – | 0/2 | 38.7 | -25.50 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 18 | A-NYAM-X2+bias | 5 | 5/0 | 40.0 | 47.9 | 51.50 | -47.33 | -7.80 | -0.086 | -6.40 | 0.73 | 77 | 2 | 0.600 | 1.000 | 1.000 | [-56.60, 41.00] | -7.80 | – | 1/2 | 47.0 | 5.50 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,mirror,p_holm) |
| 19 | A-SBAM-X1+bias | 0 | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | no trades |
| 20 | A-SBAM-X2+bias | 0 | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | no trades |
| 21 | A-SBPM-X1+bias | 4 | 4/0 | 25.0 | 35.0 | 130.00 | -70.00 | -20.00 | -0.327 | -18.50 | 0.62 | 144 | 2 | 0.642 | 1.000 | 1.000 | [-73.12, 80.38] | -20.00 | – | 0/2 | 35.4 | -40.12 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 22 | A-SBPM-X2+bias | 4 | 4/0 | 50.0 | 47.2 | 79.00 | -70.75 | 4.12 | 0.051 | 5.38 | 1.12 | 76 | 1 | 0.465 | 1.000 | 1.000 | [-70.75, 79.00] | 4.12 | – | 1/2 | 55.8 | -40.12 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 23 | A-ASIA-X1+bias | 3 | 1/2 | 66.7 | 43.7 | 60.00 | -46.50 | 24.50 | 0.967 | 25.67 | 2.58 | 46 | 1 | 0.281 | 1.000 | 1.000 | [-46.50, 65.00] | 55.00 | 9.25 | 2/3 | 80.1 | -36.83 | underpowered; no evidence of an edge (fails: underpowered,years,null,p_holm) |
| 24 | A-ASIA-X2+bias | 3 | 1/2 | 33.3 | 32.5 | 79.00 | -38.00 | 1.00 | 0.102 | 2.33 | 1.04 | 46 | 1 | 0.491 | 1.000 | 1.000 | [-46.50, 79.00] | -29.50 | 16.25 | 1/3 | 57.2 | -36.83 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 25 | B-NYAM-X1+bias | 1 | 1/0 | 100.0 | 0.0 | 159.00 | 0.00 | 159.00 | 1.988 | 160.00 | inf | 0 | 0 | 1.000 | 1.000 | 1.000 | [159.00, 159.00] | 159.00 | – | 1/1 | 72.2 | -81.50 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 26 | B-NYAM-X2+bias | 1 | 1/0 | 100.0 | 0.0 | 79.00 | 0.00 | 79.00 | 0.988 | 80.00 | inf | 0 | 0 | 1.000 | 1.000 | 1.000 | [79.00, 79.00] | 79.00 | – | 1/1 | 54.1 | -81.50 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 27 | B-ASIA-X1+bias | 1 | 0/1 | 0.0 | 100.0 | 0.00 | -40.50 | -40.50 | -1.038 | -39.00 | 0.00 | 40 | 1 | 1.000 | 1.000 | 1.000 | [-40.50, -40.50] | – | -40.50 | 0/1 | 0.0 | -40.50 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,mirror,p_holm) |
| 28 | B-ASIA-X2+bias | 1 | 0/1 | 0.0 | 100.0 | 0.00 | -40.50 | -40.50 | -1.038 | -39.00 | 0.00 | 40 | 1 | 1.000 | 1.000 | 1.000 | [-40.50, -40.50] | – | -40.50 | 0/1 | 0.0 | -40.50 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,mirror,p_holm) |
| 29 | D-NYAM-X1+bias | 341 | 226/115 | 30.8 | 32.7 | 74.03 | -36.04 | -2.15 | -0.122 | -0.80 | 0.91 | 930 | 14 | 0.763 | 1.000 | 1.000 | [-7.94, 3.91] | -0.15 | -6.07 | 4/8 | 53.3 | -15.94 | no evidence of an edge (fails: IS/OOS,null,p_holm) |
| 30 | D-NYAM-X2+bias | 341 | 226/115 | 27.3 | 29.6 | 79.00 | -33.29 | -2.67 | -0.201 | -1.30 | 0.89 | 948 | 19 | 0.830 | 1.000 | 1.000 | [-8.12, 2.89] | -3.04 | -1.93 | 3/8 | 42.1 | -16.94 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 31 | D-ASIA-X1+bias | 96 | 35/61 | 31.2 | 30.9 | 54.00 | -24.13 | 0.29 | -0.125 | 1.63 | 1.02 | 398 | 8 | 0.471 | 1.000 | 1.000 | [-7.20, 8.29] | -7.73 | 4.89 | 3/7 | 71.0 | -0.67 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 32 | D-ASIA-X2+bias | 96 | 35/61 | 22.9 | 23.8 | 76.20 | -23.86 | -0.93 | -0.165 | 0.47 | 0.95 | 506 | 19 | 0.583 | 1.000 | 1.000 | [-9.13, 7.82] | -8.96 | 3.68 | 3/7 | 55.5 | -2.19 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |

#### Confluence tests (Model A; FVG midpoint inside vs outside the 62–79% retracement; two-sided permutation)

| # | Test | n in | n out | Exp $ in | Exp $ out | Difference | p raw | p Holm | p BH | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 33 | A-NYAM-X1 conf | 5 | 58 | -16.20 | 1.01 | -17.21 | 0.642 | 1.000 | 1.000 | no evidence of a difference |
| 34 | A-NYAM-X2 conf | 5 | 58 | -17.20 | 2.53 | -19.73 | 0.558 | 1.000 | 1.000 | no evidence of a difference |
| 35 | A-SBAM-X1 conf | 1 | 11 | 79.00 | 22.00 | 57.00 | 0.828 | 1.000 | 1.000 | no evidence of a difference |
| 36 | A-SBAM-X2 conf | 1 | 11 | 79.00 | 4.91 | 74.09 | 0.830 | 1.000 | 1.000 | no evidence of a difference |
| 37 | A-SBPM-X1 conf | 1 | 11 | -41.00 | 6.86 | -47.86 | 1.000 | 1.000 | 1.000 | no evidence of a difference |
| 38 | A-SBPM-X2 conf | 1 | 11 | -41.00 | 14.09 | -55.09 | 1.000 | 1.000 | 1.000 | no evidence of a difference |
| 39 | A-ASIA-X1 conf | 2 | 17 | -43.75 | 20.32 | -64.07 | 0.185 | 1.000 | 1.000 | no evidence of a difference |
| 40 | A-ASIA-X2 conf | 2 | 17 | -43.75 | 11.00 | -54.75 | 0.269 | 1.000 | 1.000 | no evidence of a difference |

#### Monte Carlo (2000 orderings, fresh account; * = fewer trades than the horizon, resampled with replacement)

| # | Test | n | P(DD > $292 in 50 trades) | P(DD > $500 in 100 trades) |
|---|---|---|---|---|
| 1 | A-NYAM-X1 | 63 | 97.2% | 86.3%* |
| 2 | A-NYAM-X2 | 63 | 89.5% | 72.5%* |
| 3 | A-SBAM-X1 | 12 | 55.4%* | 22.9%* |
| 4 | A-SBAM-X2 | 12 | 64.7%* | 37.2%* |
| 5 | A-SBPM-X1 | 12 | 90.8%* | 80.5%* |
| 6 | A-SBPM-X2 | 12 | 67.3%* | 45.1%* |
| 7 | A-ASIA-X1 | 19 | 31.1%* | 10.4%* |
| 8 | A-ASIA-X2 | 19 | 57.2%* | 36.4%* |
| 9 | B-NYAM-X1 | 16 | 84.4%* | 72.0%* |
| 10 | B-NYAM-X2 | 16 | 93.7%* | 92.4%* |
| 11 | B-ASIA-X1 | 2 | 28.2%* | 7.4%* |
| 12 | B-ASIA-X2 | 2 | 100.0%* | 100.0%* |
| 13 | D-NYAM-X1 | 831 | 86.8% | 86.0% |
| 14 | D-NYAM-X2 | 832 | 86.9% | 82.7% |
| 15 | D-ASIA-X1 | 201 | 17.2% | 3.5% |
| 16 | D-ASIA-X2 | 201 | 36.8% | 15.1% |
| 17 | A-NYAM-X1+bias | 5 | 99.4%* | 100.0%* |
| 18 | A-NYAM-X2+bias | 5 | 91.2%* | 92.8%* |
| 21 | A-SBPM-X1+bias | 4 | 99.9%* | 99.9%* |
| 22 | A-SBPM-X2+bias | 4 | 86.1%* | 75.0%* |
| 23 | A-ASIA-X1+bias | 3 | 3.7%* | 0.2%* |
| 24 | A-ASIA-X2+bias | 3 | 70.6%* | 56.6%* |
| 25 | B-NYAM-X1+bias | 1 | 0.0%* | 0.0%* |
| 26 | B-NYAM-X2+bias | 1 | 0.0%* | 0.0%* |
| 27 | B-ASIA-X1+bias | 1 | 100.0%* | 100.0%* |
| 28 | B-ASIA-X2+bias | 1 | 100.0%* | 100.0%* |
| 29 | D-NYAM-X1+bias | 341 | 81.7% | 76.5% |
| 30 | D-NYAM-X2+bias | 341 | 81.6% | 75.5% |
| 31 | D-ASIA-X1+bias | 96 | 40.0% | 29.8%* |
| 32 | D-ASIA-X2+bias | 96 | 60.0% | 47.5%* |

#### Signal → fill funnel (per test)

| # | Test | signals | setups | stale | skip_small | skip_large | skip_leg | cancel_prearm | bias_reject | ignored_busy | ignored_losscap | armed | cancelled | expired | filled | roll_excluded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | A-NYAM-X1 | 483 | 483 | 0 | 3 | 367 | 0 | 0 | 0 | 5 | 0 | 108 | 1 | 44 | 63 | 0 |
| 2 | A-NYAM-X2 | 483 | 483 | 0 | 3 | 367 | 0 | 0 | 0 | 5 | 0 | 108 | 1 | 44 | 63 | 0 |
| 3 | A-SBAM-X1 | 114 | 114 | 0 | 0 | 84 | 0 | 0 | 0 | 1 | 0 | 29 | 0 | 17 | 12 | 0 |
| 4 | A-SBAM-X2 | 114 | 114 | 0 | 0 | 84 | 0 | 0 | 0 | 1 | 0 | 29 | 0 | 17 | 12 | 0 |
| 5 | A-SBPM-X1 | 62 | 62 | 0 | 0 | 32 | 0 | 0 | 0 | 1 | 0 | 29 | 0 | 17 | 12 | 0 |
| 6 | A-SBPM-X2 | 62 | 62 | 0 | 0 | 32 | 0 | 0 | 0 | 1 | 0 | 29 | 0 | 17 | 12 | 0 |
| 7 | A-ASIA-X1 | 71 | 71 | 0 | 3 | 30 | 0 | 0 | 0 | 1 | 0 | 37 | 0 | 18 | 19 | 0 |
| 8 | A-ASIA-X2 | 71 | 71 | 0 | 3 | 30 | 0 | 0 | 0 | 1 | 0 | 37 | 0 | 18 | 19 | 0 |
| 9 | B-NYAM-X1 | 483 | 483 | 1 | 0 | 26 | 7 | 402 | 0 | 0 | 0 | 47 | 24 | 7 | 16 | 0 |
| 10 | B-NYAM-X2 | 483 | 483 | 1 | 0 | 26 | 7 | 402 | 0 | 0 | 0 | 47 | 24 | 7 | 16 | 0 |
| 11 | B-ASIA-X1 | 71 | 71 | 0 | 0 | 1 | 14 | 46 | 0 | 0 | 0 | 10 | 6 | 2 | 2 | 0 |
| 12 | B-ASIA-X2 | 71 | 71 | 0 | 0 | 1 | 14 | 46 | 0 | 0 | 0 | 10 | 6 | 2 | 2 | 0 |
| 13 | D-NYAM-X1 | – | 2305 | 0 | 338 | 106 | 0 | 0 | 0 | 219 | 13 | 1629 | 0 | 798 | 831 | 0 |
| 14 | D-NYAM-X2 | – | 2305 | 0 | 338 | 106 | 0 | 0 | 0 | 223 | 14 | 1624 | 0 | 792 | 832 | 0 |
| 15 | D-ASIA-X1 | – | 1703 | 0 | 1091 | 4 | 0 | 0 | 0 | 62 | 4 | 542 | 0 | 341 | 201 | 0 |
| 16 | D-ASIA-X2 | – | 1703 | 0 | 1091 | 4 | 0 | 0 | 0 | 66 | 4 | 538 | 0 | 337 | 201 | 0 |
| 17 | A-NYAM-X1+bias | 483 | 483 | 0 | 3 | 367 | 0 | 0 | 105 | 0 | 0 | 8 | 0 | 3 | 5 | 0 |
| 18 | A-NYAM-X2+bias | 483 | 483 | 0 | 3 | 367 | 0 | 0 | 105 | 0 | 0 | 8 | 0 | 3 | 5 | 0 |
| 19 | A-SBAM-X1+bias | 114 | 114 | 0 | 0 | 84 | 0 | 0 | 29 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| 20 | A-SBAM-X2+bias | 114 | 114 | 0 | 0 | 84 | 0 | 0 | 29 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| 21 | A-SBPM-X1+bias | 62 | 62 | 0 | 0 | 32 | 0 | 0 | 24 | 0 | 0 | 6 | 0 | 2 | 4 | 0 |
| 22 | A-SBPM-X2+bias | 62 | 62 | 0 | 0 | 32 | 0 | 0 | 24 | 0 | 0 | 6 | 0 | 2 | 4 | 0 |
| 23 | A-ASIA-X1+bias | 71 | 71 | 0 | 3 | 30 | 0 | 0 | 34 | 0 | 0 | 4 | 0 | 1 | 3 | 0 |
| 24 | A-ASIA-X2+bias | 71 | 71 | 0 | 3 | 30 | 0 | 0 | 34 | 0 | 0 | 4 | 0 | 1 | 3 | 0 |
| 25 | B-NYAM-X1+bias | 483 | 483 | 1 | 0 | 26 | 7 | 402 | 41 | 0 | 0 | 6 | 4 | 1 | 1 | 0 |
| 26 | B-NYAM-X2+bias | 483 | 483 | 1 | 0 | 26 | 7 | 402 | 41 | 0 | 0 | 6 | 4 | 1 | 1 | 0 |
| 27 | B-ASIA-X1+bias | 71 | 71 | 0 | 0 | 1 | 14 | 46 | 7 | 0 | 0 | 3 | 2 | 0 | 1 | 0 |
| 28 | B-ASIA-X2+bias | 71 | 71 | 0 | 0 | 1 | 14 | 46 | 7 | 0 | 0 | 3 | 2 | 0 | 1 | 0 |
| 29 | D-NYAM-X1+bias | – | 2305 | 0 | 338 | 106 | 0 | 0 | 1154 | 53 | 0 | 654 | 0 | 313 | 341 | 0 |
| 30 | D-NYAM-X2+bias | – | 2305 | 0 | 338 | 106 | 0 | 0 | 1154 | 54 | 0 | 653 | 0 | 312 | 341 | 0 |
| 31 | D-ASIA-X1+bias | – | 1703 | 0 | 1091 | 4 | 0 | 0 | 370 | 17 | 0 | 221 | 0 | 125 | 96 | 0 |
| 32 | D-ASIA-X2+bias | – | 1703 | 0 | 1091 | 4 | 0 | 0 | 370 | 17 | 0 | 221 | 0 | 125 | 96 | 0 |

#### Validation

- brute_force_trades: 500
- brute_force_mismatches: 0
- lookahead_setups_checked: 5292
- rule_check_A: 100
- truncation_check_A: 20
- rule_check_B: 100
- truncation_check_B: 20
- rule_check_D: 100
- truncation_check_D: 20
- charts_check_saved: 45


Charts: `charts/equity_{primary,bias}.png` (equity curves with the IS/OOS cutoff), `charts/null_{primary,bias}.png` (null histograms), `charts/yearly_{primary,bias}.png` (net $ by year).

### Controls in plain words

- **Random-direction null:**
  - Only D-ASIA-X1 (99.8th percentile) and D-ASIA-X2 (97.0th) beat the 95th percentile.
  - D-NYAM sits at the 12th–13th percentile, worse than random entries in the same buckets.
  - All Model A and B tests sit between the 6th and 91st percentiles, which is ordinary noise.
- **Mirror:**
  - Most real tests beat their mirror, but mostly because the mirror is also negative after costs.
  - For D-NYAM, real is −$4.55 and mirrored is −$11.00: both directions lose, so beating the mirror is not evidence of an edge.
- **1H bias filter:**
  - It doesn't help. Models A and B collapse to 0–5 trades, because a sweep of highs usually happens in a bullish 1H stack, so these setups are structurally counter-trend.
  - D-NYAM with the bias filter is still negative (−$2.15 / −$2.67 over 341 trades).
- **Confluence (62–79% zone):**
  - Too few Model A entries land in the zone (1–5 per window) to say anything.
  - All 8 comparisons have p ≥ 0.185 raw and 1.000 after Holm.

### Skip and cancel counts (primary tests)

- **Model A:** 730 signals in total across the four windows.
  - **513 were skipped because the stop was over 40 pts.** The sweep extreme is usually far from the FVG midpoint, and NQ prices doubled over the sample. 6 were skipped for stops under 8 pts.
  - 203 were armed and 106 filled.
  - Only 1 cancel happened. Price can't trade beyond the sweep extreme without first passing through the FVG midpoint, so the fill always comes first except across a price gap.
- **Model B:** 554 signals.
  - 448 were invalidated during the FVG bar, before the order could be armed. That bar usually extends the leg past its far end, which is the "no retrace" cancel.
  - 21 had legs under 20 pts and 27 had stops over 40 pts.
  - 18 trades filled.
- **Model D:** 4,008 setups. 1,429 had stops under 8 pts (mostly in ASIA), 110 had stops over 40 pts, 1,032 filled (X1; 1,033 for X2), and **0 were cancelled**. The cancel rule can't trigger before a fill for the same reason as in Model A.

Full per-test counts are in the funnel table above and in `funnel_counts.csv`.

### Monte Carlo

The table above gives, for each test, the probability that a fresh account draws down more than $292 within 50 trades and more than $500 within 100 trades. For the only tests with real samples:

| Tests | P(DD > $292 in 50 trades) | P(DD > $500 in 100 trades) |
|---|---|---|
| D-NYAM | 87% | 83–86% |
| D-ASIA | 17–37% | 4–15% |

## Weaknesses of the rigid interpretation (seen in the faithfulness charts)

These are properties of the pre-registered rules, not bugs. They are why a negative result says little about discretionary ICT.

1. **MSS can be trivially satisfied.** "Most recent confirmed swing before the sweep" can be far away. If price had already trended through it, any displacement close qualifies (see `charts_check/modelB_02.png`).
2. **Sweep invalidation is only watched after the MSS** (Model B) **or after arming** (Model A). Price may already have exceeded the sweep extreme between the reclaim and the MSS.
3. **The 8–40 pt stop filter is regime-dependent.** At 2019 raw contract prices (about 7,500) most Model A stops fit. At 2025 prices (above 20,000) most don't (the adjusted series is shifted by the roll adjustments, but point ranges scale with the raw price). Sample sizes therefore drift over time, and Model A has only 6 out-of-sample NY-AM trades.
4. **Some cancel rules are inert by construction** (A and D), because the fill always comes first.

## Exploratory, not evidence

These observations come from descriptive splits made after seeing the results. They were not pre-registered and must not be used to pick a strategy.

- **D-ASIA:** the gain is concentrated in 2024–2026 (+$6.9, +$5.8 and +$9.2 per trade) after five flat or negative years. The yearly trade count rose from about 13–28 to 69, as more ASIA order blocks cleared the 8-pt minimum stop. It also does better after high-range prior days (+$7.9 per trade, n = 136). That looks like a volatility or price-level regime effect rather than a structural edge. It would need a fresh, pre-registered out-of-sample test on data after 2026-10-23 before being taken seriously.
- **Model A NY-AM by level:** ONH sweeps averaged +$45.8 (n = 20) and PDH sweeps −$26.4 (n = 24). With 20-trade cells this is noise-level, and it was never a pre-registered test.

## Amendments

None. No bugs were found after the pre-registration was frozen, and no definitions or parameters were changed.

## Files

| File | Contents |
|---|---|
| `PREREGISTRATION.md`, `PREREGISTRATION.sha256` | Frozen definitions and hash |
| `fetch_cost.py`, `fetch_data.py` | One-time Databento cost check and download (key read from a file, never printed) |
| `build_data.py` | Roll schedule, `data/roll_log.csv`, back-adjusted 1m series |
| `ict_core.py` | Bars, causal features, setup detection (A/B/D), 1m execution engine |
| `validate_ict.py` | Brute-force simulator, look-ahead, rule, truncation checks, faithfulness charts |
| `run_ict.py` | Hash check, validation gate, 40 tests, controls, statistics, Monte Carlo, charts, tables |
| `trades_ict.csv` | Every trade of all 32 standalone tests (the `label` column names the test) |
| `results_tests.csv`, `results_tables.md` | Per-test metrics and verdicts |
| `funnel_counts.csv`, `descriptive_splits.csv` | Signal → fill counts; descriptive splits (not tests) |
| `run_summary.json`, `run_log.txt` | Run metadata and log |
| `charts/`, `charts_check/` | Equity, null and yearly charts; 45 annotated faithfulness charts |
| `data/roll_log.csv`, `data/degraded_days.csv` | Roll log; Databento data-quality flags |
