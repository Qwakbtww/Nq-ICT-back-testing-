# MNQ SMT + OB spec v1: clarifications (frozen with the spec)

Answers to the 28 ambiguity questions raised on 2026-11-07, given by the spec owner before any code
was written. Together with `SPEC_v1.md` (byte-identical to the uploaded spec), this file is the
binding definition. Both are hashed in `SPEC.sha256`; every script verifies the hash and refuses to
run on a mismatch. Any later change makes a v2 with a new holdout.

Status: no SMT/OB code written, no MES data downloaded, and no signal, count or result seen when this
was frozen.

## Blockers / inputs

1. **MES data**: download Databento GLBX.MDP3 `ohlcv-1m`, parent `MES.FUT`, 2019-05-01 → 2026-10-24,
   after a free cost quote, only if the quote is ≤ $20. MNQ reuses the existing raw file
   (`backtest_ict/data/raw/MNQ_FUT_ohlcv1m_2019-05-01_2026-10-24.dbn.zst`).
2. **API key**: supplied through the session's secure credential form; never pasted in chat, printed or
   committed.
3. **Calendar file** (`calendar_skip_days.csv`):
   - built from official published schedules (BLS release schedules for the Employment Situation
     (NFP) and CPI, Federal Reserve FOMC calendars, CME Group holiday / early-close notices);
   - reviewed by the spec owner before any run, then hashed;
   - FOMC = statement (decision) days only;
   - holidays: skip CME holidays and early-close days, and also the session that opens on the evening
     of a holiday (the next trading date's overnight window).
4. **Commission**: $1.00 per contract round trip (confirmed on the Lucid dashboard: 4 contracts =
   $4.00).

## Data and contracts

5. **Roll**:
   - MNQ front month = the outright with the highest volume in the prior session (the volume flip),
     never moving back to an earlier expiry; the roll takes effect at the next 17:00 CT session open
     (the same rule as `backtest_ict/build_data.py`).
   - MES is forced onto the same contract month as MNQ.
6. **Roll exclusion**: skip signals on the roll day and the 2 trading days before and after it
   (5 trading days in total). The roll day = the trading date of the first session on the new
   contract.
7. **Prices**: raw (unadjusted) front-month prices for both instruments. No back-adjustment is needed,
   because all levels sit inside one session and roll days are excluded.
8. **Data gap**: skip a trading date if, in either instrument, two consecutive 1m bars between 17:00 CT
   (prior evening) and 11:30 CT are more than 5 minutes apart (open-to-open difference > 5 minutes).
   A missing first or last bar of the window counts too: the first bar at or after 17:00 must open by
   17:05 and the last bar before 11:30 must open at 11:25 or later.

## Window and timing

9. **Signal window**:
   - the sweep bar and the CISD bar must both be 5m bars with open ≥ 08:30 and close ≤ 11:00 CT;
   - A0/A market entries may then occur at the open of the bar after the CISD (at most 11:00);
   - B's limit may fill after 11:00 (until its 12-bar validity ends) but never at or after the forced
     exit.
10. **Forced exit**: any open trade closes at the close of the 11:29 CT 1m bar (= the 11:25–11:30 5m
    bar close), with 1 tick of slippage against the position. B limits cannot fill on or after the
    11:29 1m bar.

## Definitions

11. **Sweep (short)**: a 5m bar in the signal window that **opens at or below** MNQ's overnight high and
    whose high is ≥ the overnight high + 1 tick. A session that opens beyond the level is a gap, not a
    sweep. Longs mirror this: the bar opens at or above the overnight low, and its low is ≤ the
    overnight low − 1 tick.
12. **First sweep per side**: only the first qualifying sweep bar per side per day counts. If it gets no
    CISD within 12 bars (or the CISD falls outside the window), that side is finished for the day.
13. **Up-run**:
    - consecutive bullish 5m bars (close > open; a doji is not bullish) ending at the sweep bar, capped
      at 6 bars; it may extend before 08:30;
    - if the sweep bar is not bullish, the run ends at the bar before it;
    - an empty run (no bullish bar) → no D → no signal.
    - D = the open of the first bar of the run.
14. **Order block**: the last bullish bar of the up-run, which is the sweep bar itself when that bar is
    bullish. Zone = its body [open, close]; entry = the body midpoint.
15. **SMT (short)**: from the 08:30 CT 1m bar through the CISD bar's close, no MES 1m bar has
    high ≥ MES overnight high + 1 MES tick (0.25). Longs: no MES 1m low ≤ MES overnight low − 1 tick.
    The overnight high/low of each instrument comes from its own 1m bars in [17:00 prior evening,
    08:29] CT (inclusive of the 08:29 bar).
16. **One trade per day per test**: the first valid signal for that test (by CISD bar close time) is the
    day's only candidate. For B, if its limit does not fill, no later signal is taken that day.
    Signals with R outside 8–40 pts are skipped and count as that day's signal (no fallback).
17. **B limit**:
    - price = the body midpoint rounded to the nearest 0.25 (exact ties → the less favorable side for
      the trade: sell rounds down, buy rounds up);
    - armed at the CISD bar close; valid through the close of the 12th 5m bar after the CISD bar;
    - no cancel rule other than the expiry (and the forced exit);
    - R = |limit − stop|, filtered at arming.
    - For A0/A, R = |actual fill − stop|, filtered at the fill (no trade if outside 8–40).
18. **Stop fill**: a stop is hit when a 1m bar touches it; fill = stop price + 1 tick worse. If a bar
    opens beyond the stop, fill = that bar's open (no extra tick).
19. **Fill bar**: in the 1m bar of the entry fill only the stop is checked. Targets are rounded to the
    tick toward the entry and need a trade ≥ 1 tick through. If stop and target are both reachable in
    one 1m bar, the stop counts first.

## Pass/fail

20. **Breakeven win rate** = |avg loss R| / (avg win R + |avg loss R|), measured in the split itself
    (net of costs; includes time exits). Criterion 3 needs win rate ≥ breakeven + 3 percentage points
    and profit factor ≥ 1.15.
21. **Years criterion**: per split. Positive mean R in ≥ 60% of the split's calendar years
    (train 2019–2023: ≥ 3 of 5; validation 2024–2025: 2 of 2; holdout 2026: 1 of 1).
22. **p-value**: one-sided week-block bootstrap p for mean R > 0, matching criterion 2:
    - 10,000 resamples of whole CT calendar weeks (ISO weeks) with replacement;
    - p = the share of resampled means ≤ 0;
    - pass if p < 0.025.
    The 95% bootstrap lower bound uses the same week-block resamples (2.5th percentile).
23. **B**:
    - B passes on criteria 1–4 and 6.
    - Separately, report "OB adds value" only if B's mean R exceeds A's by ≥ 0.10 R in the split.
    - Criterion 5 (A − A0 ≥ 0.10 R) applies to A only.
24. **Holdout**: run once, only for a test that passed both train and validation. A0 is the control:
    reported, never judged.
25. **Signal counts**: may be reported per split before the single run, without P&L. Counts never
    change any rule. Fewer than 250 trades in a split = INCONCLUSIVE for that split.

## Robustness and prop simulation

26. **Sensitivity grid**:
    - one parameter changed at a time around the frozen values: stop buffer {0, 2, 4}, target
      {1.5R, 2R, 3R}, CISD window {8, 12, 16}, up-run cap {4, 6, 8};
    - train + validation only (never the holdout);
    - "fragile" = the sign of mean R flips at a one-step neighbour;
    - reported only, never used to choose anything.
27. **Lucid Flex prop simulation** (only if a test passes train and validation): 1 MNQ, day-block
    bootstrap, 10,000 paths.
    - **Flex 50K**: profit target $3,000; max loss $2,000 trailing end-of-day; $1,200 daily limit ends
      the trading day (does not fail the account); 40% consistency rule in the evaluation (largest
      single day ≤ 40% of total profit).
    - **Flex 25K**: max loss $1,000 trailing end-of-day; $600 daily limit (ends the day).
      **Profit target: PENDING owner confirmation.** The 25K simulation is not run until it is
      confirmed; this does not affect any pass/fail result.
    - Report: P(target before max loss), median days to the target, worst day, and the consistency
      check.

## Process

28. Output folder `backtest_smt/`. `RUN_LOG.md` gets one line per run (date, spec commit hash, split,
    test, trades, mean R, CI, verdict). `report.md` gets tables per test and split, R equity curves,
    and the full trade list as CSV.
    Honesty note for the report: this is the 5th study on this price history. The splits reduce
    overlap bias but do not remove it; the forward test is the real check.
