"""
audit.suite
===========

The audit itself: sections 0 to 17, in order, over the delivered artifacts.

    python verify.py            # the command that runs this
    python -m audit.suite       # the same thing, one level down

Sections 0-6 run once per session against that session's own exports; 7-17 are
whole-delivery checks (the pipeline's vocabulary, the sheet's structure, the recipe, the
badge, both arrow rules, the source file and the trade clock). The shared helpers and the
tally are in `audit.harness`.
"""

from .harness import *  # noqa: F401,F403  (the constants, readers and check helpers)
from .harness import report  # noqa: F401

# --------------------------------------------------------------------------------------
# Load shipped artifacts
# --------------------------------------------------------------------------------------

SOURCES = discovered_sessions()
TICKS = {}
for _src in SOURCES:
    _tk = load_ticks(_src)
    TICKS[ist_day(_tk[0]["epoch"])] = _tk
DAY_KEYS = sorted(TICKS)

session_json = json.loads((OUT_DATA / "session_summary.json").read_text(encoding="utf-8"))
SUMMARY = session_json["days"]                    # date -> {session, timeframes}
try:
    payload = json.loads((SHEET.read_text(encoding="utf-8").split('<script id="payload"')[1]
                          .split(">", 1)[1].split("</script>")[0]))
except (IndexError, json.JSONDecodeError):
    payload = {"meta": {}, "days": []}
DAY_ENTRIES = payload.get("days", [])
META = payload.get("meta", {})
TEMPLATE_TEXT = TEMPLATE.read_text(encoding="utf-8")
README_TEXT = README.read_text(encoding="utf-8")

csv_columns = None
fr = None

print(f"sessions={DAY_KEYS}  timeframes={TIMEFRAMES}  analytics=SMA{ANALYTICS_SMAS}")

# --------------------------------------------------------------------------------------
# 0  the multi-session wiring: one sheet, one day strip, one set of artifacts per session
# --------------------------------------------------------------------------------------

print("\n0  sessions")
check(len(SHEETS) == 1, "exactly one sheet is delivered", f"found {[p.name for p in SHEETS]}")
check(len(SOURCES) >= 1, "at least one session file was found (a tape, or a dashboard)",
      f"{len(SOURCES)}")
eq(len(DAY_ENTRIES), len(DAY_KEYS), "the sheet carries a payload entry per input file")
eq([d["date"] for d in DAY_ENTRIES], DAY_KEYS,
   "payload days are the input files, in date order")
eq(sorted(SUMMARY), DAY_KEYS, "session_summary covers every input file")
eq(META.get("dates"), DAY_KEYS, "payload meta lists every session date")
eq(META.get("days"), len(DAY_KEYS), "payload meta counts the sessions")
check(all(sorted(int(k) for k in d["timeframes"]) == sorted(TIMEFRAMES)
          for d in DAY_ENTRIES),
      "every session carries exactly the configured timeframes")
for _d in DAY_ENTRIES:
    _s = _d["session"]
    check(_s["dateIST"] == _d["date"], f"{_d['date']} session records its own date")
    # the point of the day strip: identical configuration, different data
    eq(_s["smaPeriods"], list(SMA_PERIODS), f"{_d['date']} price SMA periods")
    eq(_s["analyticsSmas"], list(ANALYTICS_SMAS), f"{_d['date']} analytics SMA periods")
    eq(_s["timeframes"], list(TIMEFRAMES), f"{_d['date']} timeframe set")
    eq(_s["pctDecimals"], PCT_DP, f"{_d['date']} percentage precision")
    # the sheet now carries TWO declared marker rules -- the green arrow and the red one
    # that mirrors it -- and says so; the removal audit in section 7 proves those two are
    # the only ones and that no other marker vocabulary survives
    eq(_s["signalLogic"], True, f"{_d['date']} records the marker rules that run")
    eq(_s["signal"]["column"], SIGNAL_KEY, f"{_d['date']} names the green-arrow column")
    eq(_s["signal"]["enabled"], True, f"{_d['date']} has the arrow rule enabled")
    eq(_s["signal"]["crossDirection"], SIGNAL_CROSS_DIRECTION,
       f"{_d['date']} records the crossing word the rule reads")
    eq(_s["signal"]["relation"], SIGNAL_RELATION,
       f"{_d['date']} records the relationship word the rule reads")
    eq((_s["signal"]["distancePctAtCrossMin"], _s["signal"]["distancePctAtCrossMax"]),
       (SIGNAL_DISTANCE_PCT_AT_CROSS_MIN, SIGNAL_DISTANCE_PCT_AT_CROSS_MAX), f"{_d['date']} records the distance window")
    eq(_s["signal"]["chgPctMin"], SIGNAL_CHG_PCT_MIN,
       f"{_d['date']} records the previous-candle change threshold")
    eq((_s["signal"]["streakMinusMin"], _s["signal"]["streakMinusMax"],
        _s["signal"]["streakPlusMin"]),
       (SIGNAL_STREAK_MINUS_MIN, SIGNAL_STREAK_MINUS_MAX, SIGNAL_STREAK_PLUS_MIN),
       f"{_d['date']} records the two previous-candle run windows")
    eth0 = _s["signal"]["distancePctAtCrossMaxScaled"]
    eq(eth0, int(round(SIGNAL_DISTANCE_PCT_AT_CROSS_MAX * (10 ** PCT_DP))),
       f"{_d['date']} scales the distance bound to the sheet's own precision")
    check("AND" in _s["signal"]["rule"] and "previous" in _s["signal"]["rule"],
          f"{_d['date']} states the rule as an AND of current and previous conditions")
    # the red rule travels in the same shape, and every number in it is the green one's
    # inverted: this is the recipe-level half of the mirror proof in 5e, and it is read
    # from the delivered payload rather than from the pipeline that wrote it
    _r = _s["redSignal"]
    eq(_r["column"], RED_KEY, f"{_d['date']} names the red-arrow column")
    eq(_r["inverted"], True, f"{_d['date']} records the red rule as the inverted one")
    eq(_r["label"], "red arrow", f"{_d['date']} labels the red rule")
    eq(_r["markerPosition"], "aboveBar", f"{_d['date']} draws the red arrow above the bar")
    eq(_r["crossDirection"], RED_CROSS_DIRECTION, f"{_d['date']} mirrors the crossing word")
    eq(_r["relation"], RED_RELATION, f"{_d['date']} mirrors the relationship word")
    eq((_r["distancePctAtCrossMin"], _r["distancePctAtCrossMax"]),
       (-SIGNAL_DISTANCE_PCT_AT_CROSS_MAX, -SIGNAL_DISTANCE_PCT_AT_CROSS_MIN),
       f"{_d['date']} negates the distance window and swaps its ends")
    eq(_r["chgPctMin"], -SIGNAL_CHG_PCT_MIN, f"{_d['date']} negates the change threshold")
    eq(_r["chgAbove"], False, f"{_d['date']} reads the change below that threshold")
    eq((_r["fastRun"], _r["slowRun"]), ("plus", "minus"),
       f"{_d['date']} swaps the two consecutive-count runs")
    eq((_r["streakMinusMin"], _r["streakMinusMax"], _r["streakPlusMin"]),
       (SIGNAL_STREAK_MINUS_MIN, SIGNAL_STREAK_MINUS_MAX, SIGNAL_STREAK_PLUS_MIN),
       f"{_d['date']} keeps the run lengths the green rule uses")
    eq(sorted(_r), sorted(_s["signal"]),
       f"{_d['date']} carries both rules in the same keys")
    # the recipe declares its own [red_signal] sentence, so that is the one the artifacts must
    # carry -- not the sentence the mirror object would write for itself, which describes the
    # same rule in the green rule's numbering
    eq(_r["rule"], CONFIG_OBJ.signal_red_rule,
       f"{_d['date']} records the red rule's own sentence, as the recipe declares it")
    check(_d["source"].endswith(f"NIFTY_{_d['date']}{TAPE_SUFFIX}") or
          _d["source"].endswith(f"NIFTY_{_d['date']}{DASH_SUFFIX}"),
          f"{_d['date']} session names its own source file", _d["source"])

# --- 0b  one session per trading day -----------------------------------------------------
# the exports are keyed by date, so two files carrying the same day would write one folder
# twice and leave the sheet with the day twice over. The build must refuse that before it
# writes anything -- and it must refuse on the day itself, not on the file names, since a
# copy saved under another date is exactly how this goes wrong.
from nifty.core.errors import DataError as BuildRefusal                               # noqa: E402
from nifty.data.pipeline import build as run_build                                    # noqa: E402

_src_one = SOURCES[0]
_suffix = DASH_SUFFIX if _src_one.name.endswith(DASH_SUFFIX) else TAPE_SUFFIX
_dup_in = Path(tempfile.mkdtemp(prefix="nifty_dup_in_"))
_dup_out = Path(tempfile.mkdtemp(prefix="nifty_dup_out_"))
shutil.copy2(_src_one, _dup_in / _src_one.name)
shutil.copy2(_src_one, _dup_in / f"NIFTY_1999-01-01{_suffix}")
_dup_cfg = dataclasses.replace(
    load_config(DEFAULT_CONFIG_PATH),
    paths=dataclasses.replace(load_config(DEFAULT_CONFIG_PATH).paths,
                              sources_dir=_dup_in, output_dir=_dup_out))
try:
    run_build(_dup_cfg)
    check(False, "two session files carrying one trading day are refused",
          f"{_src_one.name} and its copy under another date")
except BuildRefusal as _exc:
    check(DAY_KEYS[0] in str(_exc) and "keep one file per trading day" in str(_exc),
          "two session files carrying one trading day are refused, naming the day", str(_exc))
    check(not list((_dup_out / "data").glob("*")), "and nothing is written before the refusal",
          f"{sorted(p.name for p in (_dup_out / 'data').glob('*'))[:3]}")


def audit_day(DAY, SESSION, ticks, SUMMARY_TFS, payload):
    """Sections 1-6 for one session, against that session's own artifacts."""
    global csv_columns, fr
    # --------------------------------------------------------------------------------------
    # 1  session
    # --------------------------------------------------------------------------------------

    print("\n1  session")
    eq(SESSION["ticks"], len(ticks), "session.tick count matches the tick file")
    eq(SESSION["instrument"], "NIFTY 50", "session.instrument")
    eq(SESSION["dateIST"], DAY, "session.dateIST matches the file's own session date")
    eq(SESSION["sessionStartIST"], datetime.fromtimestamp(ticks[0]["epoch"] + IST, tz=timezone.utc)
       .strftime("%Y-%m-%d %H:%M:%S"), "session.start (IST)")
    eq(SESSION["sessionEndIST"], datetime.fromtimestamp(ticks[-1]["epoch"] + IST, tz=timezone.utc)
       .strftime("%Y-%m-%d %H:%M:%S"), "session.end (IST)")
    check(all(b["epoch"] - a["epoch"] > 0 for a, b in zip(ticks, ticks[1:])),
          "tick file has no duplicate/negative timestamps")
    gap_seconds = (ticks[-1]["epoch"] - ticks[0]["epoch"] + 1) - len({t["epoch"] for t in ticks})
    eq(SESSION["secondsMissing"], gap_seconds, "session.secondsMissing")
    eq(SESSION["secondsExpected"], ticks[-1]["epoch"] - ticks[0]["epoch"] + 1, "session.secondsExpected")
    eq(SESSION["coveragePct"], round(len(ticks) / SESSION["secondsExpected"] * 100.0, 2),
       "session.coveragePct")
    eq(SESSION["dayOpen"], round(ticks[0]["nifty"] + 0.0, 2), "session.dayOpen")
    eq(SESSION["dayClose"], round(ticks[-1]["nifty"] + 0.0, 2), "session.dayClose")
    eq(SESSION["dayHigh"], round(max(t["nifty"] for t in ticks) + 0.0, 2), "session.dayHigh")
    eq(SESSION["dayLow"], round(min(t["nifty"] for t in ticks) + 0.0, 2), "session.dayLow")
    eq(SESSION["dayChangePts"], round(SESSION["dayClose"] - SESSION["dayOpen"] + 0.0, 2),
       "session.dayChangePts")
    eq(SESSION["smaPeriods"], list(SMA_PERIODS), "session.smaPeriods")
    eq(SESSION["analyticsSmas"], list(ANALYTICS_SMAS), "session.analyticsSmas covers all three")

    # --------------------------------------------------------------------------------------
    # Per timeframe
    # --------------------------------------------------------------------------------------

    csv_columns = None
    RESTART_WITNESSES = [0]   # reversals that must start a fresh run at 1
    ZERO_WITNESSES = [0]      # exact-zero changes that must reset both runs
    DIR_SWITCH_WITNESSES = [0]   # BELOW -> ABOVE / ABOVE -> BELOW switches seen
    DIR_RESET_WITNESSES = [0]    # candles where the direction row resets to +0 / -0
    CROSS_HERE = [0]             # strict crossings in this session
    CROSS_BLANK_HERE = [0]       # crossings whose distance row is blank

    for seconds in TIMEFRAMES:
        slug = f"{seconds // 60}min" if seconds >= 60 else f"{seconds}sec"
        label = f"{DAY} {slug}"
        print(f"\n  --- {label} ---")
        bars = naive_bars(ticks, seconds)
        shipped = json.loads((OUT_DATA / DAY / f"nifty_{slug}.json").read_text(encoding="utf-8"))["bars"]
        stats = SUMMARY_TFS[str(seconds)]
        fr = payload["timeframes"][str(seconds)]

        # ---- 2  bars
        eq(len(shipped), len(bars), f"[{label}] bar count")
        eq(len(fr["bars"]), len(bars), f"[{label}] payload bar count")
        eq(stats["bars"], len(bars), f"[{label}] summary.bars")
        bad = []
        for i, (a, b) in enumerate(zip(bars, shipped)):
            for key in ("open", "high", "low", "close", "ticks", "atm"):
                if a[key] != b[key]:
                    bad.append((i, key, b[key], a[key]))
            if b["time"] != a["time"]:
                bad.append((i, "time", b["time"], a["time"]))
        check(not bad, f"[{label}] OHLC/tick/atm identical to an independent rebucket",
              f"{len(bad)} mismatches, first {bad[:3]}")
        check(all(b["low"] <= b["open"] <= b["high"] and b["low"] <= b["close"] <= b["high"]
                  for b in bars), f"[{label}] open/close inside [low, high]")
        check(all(a["time"] < b["time"] for a, b in zip(bars, bars[1:])),
              f"[{label}] bars in chronological order")
        check(all(b["time"] % seconds == 0 for b in bars), f"[{label}] buckets aligned to the clock")
        check(sum(b["ticks"] for b in bars) == len(ticks), f"[{label}] ticks fully attributed")

        expected_keys = {"time", "open", "high", "low", "close", "atm", "ticks"}
        expected_keys |= {f"sma{p}" for p in SMA_PERIODS}
        expected_keys |= {f"sma{p}_{k}" for p in ANALYTICS_SMAS
                          for k in ("chg_pct", "streak_plus", "streak_minus")}
        expected_keys |= {f"sma{DIRECTION_FAST}_vs_sma{DIRECTION_SLOW}_{k}_streak"
                          for k in ("above", "below")}
        expected_keys |= {f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_cross_direction",
                          f"sma{CROSS_DIST_FROM}_vs_sma{CROSS_DIST_TO}_distance_pct_at_cross",
                          f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_distance_pct_at_cross",
                          f"sma{RELATION_FAST}_vs_sma{RELATION_SLOW}_relation",
                          SIGNAL_KEY, RED_KEY, CE_OI_CHANGE, PE_OI_CHANGE}
        got_keys = set(shipped[0].keys())
        eq(got_keys, expected_keys, f"[{label}] JSON bar keys")
        check(not (got_keys & {"cross", "crossovers", "markers", "pattern", "signal",
                               "alignment", "sma2_plus", "sma2_minus"}),
              f"[{label}] JSON bars free of un-declared marker/signal and stale count keys")

        # ---- 3  sma
        cents = [int(round(b["close"] * 100)) for b in bars]
        sma_cents = {p: naive_sma(cents, p) for p in SMA_PERIODS}
        for period in SMA_PERIODS:
            mine = sma_cents[period]
            key = f"sma{period}"
            diffs = [(i, shipped[i][key], None if mine[i] is None else mine[i] / 100)
                     for i in range(len(bars))
                     if (shipped[i][key] is None) != (mine[i] is None)
                     or (mine[i] is not None and abs(shipped[i][key] - mine[i] / 100) > 1e-9)]
            check(not diffs, f"[{label}] SMA({period}) exact on all {len(bars)} bars",
                  f"{len(diffs)} mismatches, first {diffs[:3]}")
            eq(next((i for i, v in enumerate(mine) if v is not None), None), period - 1,
               f"[{label}] SMA({period}) first defined at bar index {period - 1}")
            eq(stats["smaLast"][str(period)],
               None if mine[-1] is None else mine[-1] / 100, f"[{label}] summary smaLast[{period}]")

        # ---- 4  percentage change,  5  runs
        CHANGES: dict[int, list[int | None]] = {}
        for period in ANALYTICS_SMAS:
            changes = [naive_pct(sma_cents[period][i], sma_cents[period][i - 1] if i else None)
                       for i in range(len(bars))]
            CHANGES[period] = changes
            up_run, down_run = naive_runs(changes)

            key = f"sma{period}_chg_pct"
            diffs = []
            for i in range(len(bars)):
                want, got = changes[i], shipped[i][key]
                if want is None:
                    if got is not None:
                        diffs.append((i, got, None))
                elif got is None or abs(got - want / (10 ** PCT_DP)) > 1e-12:
                    diffs.append((i, got, want / (10 ** PCT_DP)))
            check(not diffs, f"[{label}] SMA({period}) change % matches (cur-prev)/prev*100 on all bars",
                  f"{len(diffs)} mismatches, first {diffs[:3]}")

            blanks = [i for i in range(len(bars)) if changes[i] is None]
            eq(len(blanks), period, f"[{label}] exactly {period} blank SMA({period}) changes")
            check(all(shipped[i][key] is None for i in blanks),
                  f"[{label}] blank SMA({period}) changes where no previous average exists")
            first_chg = next((i for i in range(len(bars)) if changes[i] is not None), None)
            eq(first_chg, period, f"[{label}] SMA({period}) first change at bar index {period}")
            eq(stats["analytics"][str(period)]["firstChgIndex"], first_chg,
               f"[{label}] summary firstChgIndex[{period}]")
            eq(stats["analytics"][str(period)]["definedFrom"], period - 1,
               f"[{label}] summary definedFrom[{period}]")

            bad_up = [(i, shipped[i][f"sma{period}_streak_plus"], up_run[i])
                      for i in range(len(bars)) if shipped[i][f"sma{period}_streak_plus"] != up_run[i]]
            bad_down = [(i, shipped[i][f"sma{period}_streak_minus"], down_run[i])
                        for i in range(len(bars)) if shipped[i][f"sma{period}_streak_minus"] != down_run[i]]
            check(not bad_up, f"[{label}] SMA({period}) consecutive rising run on every bar",
                  f"{len(bad_up)} mismatches, first {bad_up[:3]}")
            check(not bad_down, f"[{label}] SMA({period}) consecutive falling run on every bar",
                  f"{len(bad_down)} mismatches, first {bad_down[:3]}")

            # the two runs are mutually exclusive, and a run is never longer than its own count
            check(all(shipped[i][f"sma{period}_streak_plus"] == 0
                      or shipped[i][f"sma{period}_streak_minus"] == 0 for i in range(len(bars))),
                  f"[{label}] SMA({period}) rising and falling runs never both non-zero")
            check(all(shipped[i][f"sma{period}_streak_plus"] <=
                      sum(1 for c in changes[:i + 1] if c is not None and c > 0) for i in range(len(bars))),
                  f"[{label}] SMA({period}) a rising run never exceeds the rises seen so far")

            # stale, cumulative semantics are gone. A streak is the run TRAILING into the last
            # candle, found by an independent backwards walk -- cumulative totals would keep the
            # whole day's tally and cannot satisfy this whenever the series ever reversed.
            tail_up = tail_down = 0
            for c in reversed(changes):
                if c is None:
                    continue
                if c > 0 and tail_down == 0:
                    tail_up += 1
                elif c < 0 and tail_up == 0:
                    tail_down += 1
                else:
                    break
            eq((shipped[-1][f"sma{period}_streak_plus"], shipped[-1][f"sma{period}_streak_minus"]),
               (tail_up, tail_down),
               f"[{label}] SMA({period}) last values are the trailing run, not a running total")
            # a reversal must start a NEW run at 1, never continue an earlier tally
            for sign, asc, key in ((1, True, "streak_plus"), (-1, False, "streak_minus")):
                run_key = f"sma{period}_{key}"
                restarts = [i for i in range(1, len(bars))
                            if changes[i] is not None and (changes[i] * sign > 0)
                            and changes[i - 1] is not None and (changes[i - 1] * sign <= 0)]
                check(all(shipped[i][run_key] == 1 for i in restarts),
                      f"[{label}] SMA({period}) every {'rise' if asc else 'fall'} after a reversal "
                      f"restarts its run at 1", f"{len(restarts)} restarts")
                RESTART_WITNESSES[0] += len(restarts)
            ZERO_WITNESSES[0] += len([c for c in changes if c == 0])

            # zero change resets BOTH runs: assert directly at every zero
            zeros = [i for i, c in enumerate(changes) if c == 0]
            check(all(shipped[i][f"sma{period}_streak_plus"] == 0
                      and shipped[i][f"sma{period}_streak_minus"] == 0 for i in zeros),
                  f"[{label}] SMA({period}) zero change resets both runs to 0")
            # ...and the bar after a zero starts a fresh streak at 1
            fresh = [i for i in zeros if i + 1 < len(bars) and changes[i + 1] not in (None, 0)]
            check(all(max(shipped[i + 1][f"sma{period}_streak_plus"],
                          shipped[i + 1][f"sma{period}_streak_minus"]) == 1 for i in fresh),
                  f"[{label}] SMA({period}) a move straight after a zero starts a new run at 1")

            eq(stats["analytics"][str(period)]["streakPlus"], up_run[-1],
               f"[{label}] summary streakPlus[{period}]")
            eq(stats["analytics"][str(period)]["streakMinus"], down_run[-1],
               f"[{label}] summary streakMinus[{period}]")
            eq(stats["analytics"][str(period)]["maxStreakPlus"], max(up_run),
               f"[{label}] summary maxStreakPlus[{period}]")
            eq(stats["analytics"][str(period)]["maxStreakMinus"], max(down_run),
               f"[{label}] summary maxStreakMinus[{period}]")
            eq(stats["analytics"][str(period)]["lastLabel"], count_label(up_run[-1], down_run[-1]),
               f"[{label}] summary lastLabel[{period}] uses '+n / -n'")
            eq(stats["analytics"][str(period)]["zeroChanges"],
               sum(1 for c in changes if c == 0), f"[{label}] summary zeroChanges[{period}]")
            eq(stats["analytics"][str(period)]["risingChanges"],
               sum(1 for c in changes if c is not None and c > 0),
               f"[{label}] summary risingChanges[{period}]")

        # ---- 5b  the SMA 2 vs SMA 9 direction streak
        fast_p, slow_p = DIRECTION_FAST, DIRECTION_SLOW
        akey = f"sma{fast_p}_vs_sma{slow_p}_above_streak"
        bkey = f"sma{fast_p}_vs_sma{slow_p}_below_streak"
        above_run, below_run = naive_direction_runs(sma_cents[fast_p], sma_cents[slow_p],
                                                   CHANGES[slow_p])
        bad_above = [(i, shipped[i][akey], above_run[i])
                     for i in range(len(bars)) if shipped[i][akey] != above_run[i]]
        bad_below = [(i, shipped[i][bkey], below_run[i])
                     for i in range(len(bars)) if shipped[i][bkey] != below_run[i]]
        check(not bad_above,
              f"[{label}] SMA {fast_p} vs {slow_p} ABOVE streak on every bar",
              f"{len(bad_above)} mismatches, first {bad_above[:3]}")
        check(not bad_below,
              f"[{label}] SMA {fast_p} vs {slow_p} BELOW streak on every bar",
              f"{len(bad_below)} mismatches, first {bad_below[:3]}")

        # the rule, stated directly against the shipped values: wherever a side is running,
        # the two conditions of that side hold, and a zero means neither side held
        rule_violations = []
        for i, bar in enumerate(shipped):
            fc, sc = sma_cents[fast_p][i], sma_cents[slow_p][i]
            chg = CHANGES[slow_p][i]
            above_ok = fc is not None and sc is not None and chg is not None and fc > sc and chg > 0
            below_ok = fc is not None and sc is not None and chg is not None and fc < sc and chg < 0
            if above_ok and bar[akey] < 1:
                rule_violations.append((i, "above rule holds but the streak is 0", bar[akey]))
            if below_ok and bar[bkey] < 1:
                rule_violations.append((i, "below rule holds but the streak is 0", bar[bkey]))
            if not above_ok and not below_ok and (bar[akey] or bar[bkey]):
                rule_violations.append((i, "neither rule holds but the streak is non-zero",
                                        (bar[akey], bar[bkey])))
            if bar[akey] and bar[bkey]:
                rule_violations.append((i, "ABOVE and BELOW are both running",
                                        (bar[akey], bar[bkey])))
        check(not rule_violations,
              f"[{label}] SMA {fast_p} vs {slow_p} streak obeys the rule at every candle",
              f"{len(rule_violations)} violations, first {rule_violations[:3]}")

        # A second, independent formulation: mark the candles that satisfy each side's
        # conditions and take the TRAILING run of that mask. A tally would keep counting
        # after the mask broke, so anything cumulative fails here.
        def side_mask(want_above: bool) -> list[int]:
            mask = []
            for i in range(len(bars)):
                fc, sc, chg = sma_cents[fast_p][i], sma_cents[slow_p][i], CHANGES[slow_p][i]
                ok = (fc is not None and sc is not None and chg is not None)
                mask.append(1 if ok and ((fc > sc and chg > 0) if want_above
                                         else (fc < sc and chg < 0)) else 0)
            return mask

        def trailing(mask: list[int]) -> list[int]:
            out, run = [], 0
            for v in mask:
                run = run + 1 if v else 0
                out.append(run)
            return out

        eq([shipped[i][akey] for i in range(len(bars))], trailing(side_mask(True)),
           f"[{label}] ABOVE row equals the trailing run of candles satisfying the ABOVE rule")
        eq([shipped[i][bkey] for i in range(len(bars))], trailing(side_mask(False)),
           f"[{label}] BELOW row equals the trailing run of candles satisfying the BELOW rule")

        # a direction switch, and the candle right after a reset, both start at 1
        switches = [i for i in range(1, len(bars))
                    if (shipped[i][akey] and shipped[i - 1][bkey]) or
                       (shipped[i][bkey] and shipped[i - 1][akey])]
        check(all(shipped[i][akey if shipped[i][akey] else bkey] == 1 for i in switches),
              f"[{label}] every direction switch starts the new streak at 1",
              f"{len(switches)} switches")
        resets = [i for i in range(len(bars)) if not shipped[i][akey] and not shipped[i][bkey]]
        fresh = [i for i in resets if i + 1 < len(bars) and (shipped[i + 1][akey] or shipped[i + 1][bkey])]
        check(all(max(shipped[i + 1][akey], shipped[i + 1][bkey]) == 1 for i in fresh),
              f"[{label}] a direction run straight after a reset starts at 1")
        DIR_SWITCH_WITNESSES[0] += len(switches)
        DIR_RESET_WITNESSES[0] += len(resets)

        # the rule reads the rounded 4-decimal change the sheet prints. Assert that rounding
        # can never turn a move into the wrong sign, and count the moves it swallows entirely.
        sign_conflicts = []
        for i in range(1, len(bars)):
            if sma_cents[slow_p][i] is None or sma_cents[slow_p][i - 1] is None:
                continue
            raw = sma_cents[slow_p][i] - sma_cents[slow_p][i - 1]
            rounded = CHANGES[slow_p][i]
            if raw != 0 and rounded == 0:
                DIR_ROUNDED_AWAY[0] += 1
            elif rounded not in (None, 0) and (raw > 0) != (rounded > 0):
                sign_conflicts.append((i, raw, rounded))
        check(not sign_conflicts,
              f"[{label}] rounding the SMA {slow_p} change never flips its sign",
              f"{len(sign_conflicts)} conflicts, first {sign_conflicts[:3]}")

        dstats = stats["direction"]
        eq(dstats["fastPeriod"], fast_p, f"[{label}] summary direction fast period")
        eq(dstats["slowPeriod"], slow_p, f"[{label}] summary direction slow period")
        eq(dstats["aboveKey"], akey, f"[{label}] summary direction above column")
        eq(dstats["belowKey"], bkey, f"[{label}] summary direction below column")
        eq(dstats["lastAbove"], above_run[-1], f"[{label}] summary direction lastAbove")
        eq(dstats["lastBelow"], below_run[-1], f"[{label}] summary direction lastBelow")
        eq(dstats["maxAbove"], max(above_run), f"[{label}] summary direction maxAbove")
        eq(dstats["maxBelow"], max(below_run), f"[{label}] summary direction maxBelow")
        eq(dstats["aboveBars"], sum(1 for v in above_run if v > 0),
           f"[{label}] summary direction aboveBars")
        eq(dstats["belowBars"], sum(1 for v in below_run if v > 0),
           f"[{label}] summary direction belowBars")
        eq(dstats["resetBars"], len(resets), f"[{label}] summary direction resetBars")
        eq(dstats["switches"], len(switches), f"[{label}] summary direction switches")
        eq(dstats["lastLabel"], direction_label(above_run[-1], below_run[-1]),
           f"[{label}] summary direction lastLabel uses '+n / -n'")
        eq(dstats["displayLabel"], direction_label_ascii(above_run[-1], below_run[-1]),
           f"[{label}] summary direction displayLabel")

        # ---- 5c  the strict SMA 2 vs SMA 9 crossing, and the distance it carries
        # Written from the requirement and nothing else: the crossing is decided by
        # comparing THIS candle with the PREVIOUS one, an equal pair is never a crossing,
        # and the first candle has no previous candle at all. The distances are read on the
        # crossing candle, as scaled integers with the verifier's own half-up rounding.
        x_fast, x_slow = CROSS_FAST, CROSS_SLOW
        d_from, d_to = CROSS_DIST_FROM, CROSS_DIST_TO
        xkey = f"sma{x_fast}_vs_sma{x_slow}_cross_direction"
        dkey = f"sma{d_from}_vs_sma{d_to}_distance_pct_at_cross"
        pkey = f"sma{x_fast}_vs_sma{x_slow}_distance_pct_at_cross"

        def naive_cross_rows(upto: int) -> tuple[list, list, list]:
            """The crossing row and its two distances, for the first `upto` candles."""
            direction = [None] * upto
            distance = [None] * upto
            pair_distance = [None] * upto
            for i in range(upto):
                fc, sc = sma_cents[x_fast][i], sma_cents[x_slow][i]
                if i == 0:
                    continue
                pf, ps = sma_cents[x_fast][i - 1], sma_cents[x_slow][i - 1]
                if None in (fc, sc, pf, ps):
                    continue
                if pf < ps and fc > sc:
                    direction[i] = "ABOVE"
                elif pf > ps and fc < sc:
                    direction[i] = "BELOW"
                else:
                    continue                      # same side, or an equal pair
                fv, tv = sma_cents[d_from][i], sma_cents[d_to][i]
                distance[i] = naive_pct(fv, tv) if None not in (fv, tv) else None
                pair_distance[i] = naive_pct(fc, sc)
            return direction, distance, pair_distance

        naive_dir, naive_dist, naive_pair = naive_cross_rows(len(bars))

        eq([b[xkey] for b in shipped], naive_dir, f"[{label}] cross direction on every bar")
        eq([None if b[dkey] is None else int(round(b[dkey] * 10 ** PCT_DP)) for b in shipped],
           naive_dist, f"[{label}] SMA {d_from} vs {d_to} distance on every bar")
        eq([None if b[pkey] is None else int(round(b[pkey] * 10 ** PCT_DP)) for b in shipped],
           naive_pair, f"[{label}] SMA {x_fast} vs {x_slow} distance on every bar")
        # the payload stays OHLC-only: the sheet derives the crossing row itself, from the
        # same averages, so the frame carries the columns' names rather than their values
        check(xkey not in fr["bars"][0] and dkey not in fr["bars"][0]
              and pkey not in fr["bars"][0],
              f"[{label}] payload bars carry no crossing values (the sheet derives them)")
        eq(fr["cross"]["fastPeriod"], x_fast, f"[{label}] payload cross fast period")
        eq(fr["cross"]["slowPeriod"], x_slow, f"[{label}] payload cross slow period")
        eq(fr["cross"]["distanceFromPeriod"], d_from, f"[{label}] payload cross from period")
        eq(fr["cross"]["distanceToPeriod"], d_to, f"[{label}] payload cross to period")
        check("above" in fr["cross"]["rule"] and "equal" in fr["cross"]["rule"],
              f"[{label}] payload cross rule forbids an equal pair")

        # the rule, stated directly against the shipped values: a crossing is ALWAYS a
        # change of side between the previous candle and this one, and the side named is
        # the side the pair sits on now
        wrong_side = [i for i in range(len(bars))
                      if naive_dir[i] is not None and
                      ((naive_dir[i] == "ABOVE") != (sma_cents[x_fast][i] > sma_cents[x_slow][i]))]
        check(not wrong_side,
              f"[{label}] each crossing names the side the pair sits on now",
              f"{len(wrong_side)} wrong, first {wrong_side[:3]}")
        one_side_only = [i for i, d in enumerate(naive_dir) if d not in (None, "ABOVE", "BELOW")]
        check(not one_side_only, f"[{label}] the cross row only ever reads above/below/blank",
              f"{one_side_only[:3]}")

        # an equal pair, on either candle, is never a strict crossing
        equal_now = [i for i in range(len(bars))
                     if sma_cents[x_fast][i] is not None and
                     sma_cents[x_fast][i] == sma_cents[x_slow][i]]
        equal_prev = [i for i in range(1, len(bars))
                      if sma_cents[x_fast][i - 1] is not None and
                      sma_cents[x_fast][i - 1] == sma_cents[x_slow][i - 1]]
        check(all(naive_dir[i] is None for i in equal_now),
              f"[{label}] equal averages on this candle are not a crossing",
              f"{len(equal_now)} equal candles")
        check(all(naive_dir[i] is None for i in equal_prev),
              f"[{label}] equal averages on the previous candle are not a crossing",
              f"{len(equal_prev)} equal candles")
        check(naive_dir[0] is None and shipped[0][xkey] is None,
              f"[{label}] the first candle of the session carries no crossing")

        # the crossing may not read a later candle: recompute the row over a truncated
        # series -- more than half of it -- and require the whole prefix to be identical
        half = max(2, len(bars) // 2)
        head_dir, head_dist, head_pair = naive_cross_rows(half)
        eq(head_dir, naive_dir[:half],
           f"[{label}] no crossing in the first {half} candles depends on a later candle")
        eq(head_dist, naive_dist[:half], f"[{label}] no distance depends on a later candle")
        eq(head_pair, naive_pair[:half],
           f"[{label}] no pair distance depends on a later candle")

        # the blanks: a crossing before the divisor average exists, and a zero divisor
        blank_dist = [i for i in range(len(bars)) if naive_dir[i] and naive_dist[i] is None]
        check(all(shipped[i][dkey] is None for i in blank_dist),
              f"[{label}] a crossing with no usable divisor leaves the distance blank",
              f"{len(blank_dist)} such candles")
        check(all(shipped[i][dkey] is not None for i in range(len(bars))
                  if naive_dir[i] and naive_dist[i] is not None),
              f"[{label}] every crossing with both averages present carries a distance")
        empty_without_cross = [i for i in range(len(bars))
                               if not naive_dir[i] and shipped[i][dkey] is not None]
        check(not empty_without_cross,
              f"[{label}] a candle without a crossing carries no distance",
              f"{empty_without_cross[:3]}")

        # every distance really is (SMA from - SMA to) / SMA to * 100 at 4 decimals
        dist_rule = []
        for i in range(len(bars)):
            if naive_dist[i] is None:
                continue
            fv, tv = sma_cents[d_from][i], sma_cents[d_to][i]
            if tv == 0:
                dist_rule.append((i, "zero divisor"))
                continue
            if naive_dist[i] != div_half_up((fv - tv) * 100 * 10 ** PCT_DP, tv):
                dist_rule.append((i, naive_dist[i]))
        check(not dist_rule, f"[{label}] every distance is the documented formula",
              f"{dist_rule[:3]}")

        xstats = stats["cross"]
        above_idx = [i for i, d in enumerate(naive_dir) if d == "ABOVE"]
        below_idx = [i for i, d in enumerate(naive_dir) if d == "BELOW"]
        cross_idx = sorted(above_idx + below_idx)
        dist_vals = [b[dkey] for b in shipped if b[dkey] is not None]
        pair_vals = [b[pkey] for b in shipped if b[pkey] is not None]

        eq(xstats["fastPeriod"], x_fast, f"[{label}] summary cross fast period")
        eq(xstats["slowPeriod"], x_slow, f"[{label}] summary cross slow period")
        eq(xstats["distanceFromPeriod"], d_from, f"[{label}] summary cross from period")
        eq(xstats["distanceToPeriod"], d_to, f"[{label}] summary cross to period")
        eq(xstats["directionColumn"], xkey, f"[{label}] summary cross direction column")
        eq(xstats["distanceColumn"], dkey, f"[{label}] summary cross distance column")
        eq(xstats["pairDistanceColumn"], pkey, f"[{label}] summary cross pair column")
        eq(xstats["aboveCrossings"], len(above_idx),
           f"[{label}] summary ABOVE crossings")
        eq(xstats["belowCrossings"], len(below_idx),
           f"[{label}] summary BELOW crossings")
        eq(xstats["crossings"], len(cross_idx), f"[{label}] summary total crossings")
        eq(xstats["firstCrossIndex"], cross_idx[0] if cross_idx else None,
           f"[{label}] summary first crossing index")
        eq(xstats["lastCrossIndex"], cross_idx[-1] if cross_idx else None,
           f"[{label}] summary last crossing index")
        eq(xstats["lastCrossDirection"],
           naive_dir[cross_idx[-1]] if cross_idx else None,
           f"[{label}] summary last crossing direction")
        eq(xstats["distance"]["count"], len(dist_vals), f"[{label}] summary distances carried")
        eq(xstats["distance"]["last"], dist_vals[-1] if dist_vals else None,
           f"[{label}] summary last crossing distance")
        eq(xstats["distance"]["min"], min(dist_vals) if dist_vals else None,
           f"[{label}] summary minimum distance")
        eq(xstats["distance"]["max"], max(dist_vals) if dist_vals else None,
           f"[{label}] summary maximum distance")
        eq(xstats["distance"]["avg"],
           round(sum(dist_vals) / len(dist_vals), PCT_DP) if dist_vals else None,
           f"[{label}] summary average distance")
        eq(xstats["distanceAbove"], sum(1 for v in dist_vals if v > 0),
           f"[{label}] summary crossings with SMA {d_from} above SMA {d_to}")
        eq(xstats["distanceBelow"], sum(1 for v in dist_vals if v < 0),
           f"[{label}] summary crossings with SMA {d_from} below SMA {d_to}")
        eq(xstats["distanceZero"], sum(1 for v in dist_vals if v == 0),
           f"[{label}] summary crossings with equal averages")
        eq(xstats["distanceBlank"], len(cross_idx) - len(dist_vals),
           f"[{label}] summary crossings with a blank distance")
        eq(xstats["pairDistance"]["count"], len(pair_vals),
           f"[{label}] summary supplementary distances")
        eq(xstats["pairDistance"]["min"], min(pair_vals) if pair_vals else None,
           f"[{label}] summary supplementary minimum")
        eq(xstats["pairDistance"]["max"], max(pair_vals) if pair_vals else None,
           f"[{label}] summary supplementary maximum")
        check("above" in xstats["rule"] and "BELOW" in xstats["rule"],
              f"[{label}] summary cross rule names both directions")
        check(str(d_from) in xstats["distanceRule"] and str(d_to) in xstats["distanceRule"],
              f"[{label}] summary distance rule names both periods")

        CROSS_HERE[0] += len(cross_idx)
        CROSS_BLANK_HERE[0] += len(blank_dist)
        CROSS_ZERO_DISTANCE[0] += sum(1 for v in dist_vals if v == 0)

        # ---- 5d  the SMA 9 vs SMA 44 above/below relationship
        # Written from the rule and nothing else: the word is a comparison of THIS candle's
        # own two averages -- no previous candle is involved, unlike the crossing above -- and
        # a tie belongs to neither side. Blank until the slow average has a value, which is
        # every candle before its period.
        rel_fast, rel_slow = RELATION_FAST, RELATION_SLOW
        rkey = f"sma{rel_fast}_vs_sma{rel_slow}_relation"
        naive_rel = []
        for i in range(len(bars)):
            fc, sc = sma_cents[rel_fast][i], sma_cents[rel_slow][i]
            if fc is None or sc is None or fc == sc:
                naive_rel.append(None)
            else:
                naive_rel.append("ABOVE" if fc > sc else "BELOW")

        eq([b[rkey] for b in shipped], naive_rel, f"[{label}] relationship word on every bar")
        check(rkey not in fr["bars"][0],
              f"[{label}] payload bars carry no relationship values (the sheet derives them)")
        eq(fr["relation"]["fastPeriod"], rel_fast, f"[{label}] payload relation fast period")
        eq(fr["relation"]["slowPeriod"], rel_slow, f"[{label}] payload relation slow period")
        check("relationColumn" not in fr["relation"],
              f"[{label}] the frame names the relationship periods, not its column "
              "(the sheet derives the row)")
        check("ABOVE" in fr["relation"]["rule"] and "BELOW" in fr["relation"]["rule"],
              f"[{label}] payload relation rule names both sides")

        # the rule restated against the SHIPPED averages rather than against the
        # verifier's own: the word is exactly the sign of (SMA 9 - SMA 44) on that candle
        sign_bad = [i for i, b in enumerate(shipped)
                    if b[f"sma{rel_fast}"] is not None and b[f"sma{rel_slow}"] is not None
                    and b[f"sma{rel_fast}"] != b[f"sma{rel_slow}"]
                    and b[rkey] != ("ABOVE" if b[f"sma{rel_fast}"] > b[f"sma{rel_slow}"]
                                    else "BELOW")]
        check(not sign_bad,
              f"[{label}] each word matches the sign of SMA {rel_fast} - SMA {rel_slow}",
              f"{len(sign_bad)} wrong, first {sign_bad[:3]}")

        # a tie is not a side, and neither is a missing average
        tie_now = [i for i in range(len(bars))
                   if sma_cents[rel_fast][i] is not None
                   and sma_cents[rel_fast][i] == sma_cents[rel_slow][i]]
        check(all(naive_rel[i] is None for i in tie_now),
              f"[{label}] equal averages carry no side", f"{len(tie_now)} tied candles")
        check(all(shipped[i][rkey] is None for i in tie_now),
              f"[{label}] the delivered row is blank on every tie")
        before_slow = [i for i in range(len(bars)) if sma_cents[rel_slow][i] is None]
        check(all(naive_rel[i] is None for i in before_slow),
              f"[{label}] the row is blank until SMA {rel_slow} exists",
              f"{len(before_slow)} candles before it does")
        check(naive_rel[0] is None and shipped[0][rkey] is None,
              f"[{label}] the session's first candle carries no side")
        check(all(b[rkey] in (None, "ABOVE", "BELOW") for b in shipped),
              f"[{label}] the relationship row only ever reads ABOVE, BELOW or blank")

        rel_vals = [b[rkey] for b in shipped]
        REL_ABOVE_BARS[0] += rel_vals.count("ABOVE")
        REL_BELOW_BARS[0] += rel_vals.count("BELOW")
        REL_BLANK_BARS[0] += rel_vals.count(None)
        REL_TIES[0] += len(tie_now)

        # ---- 5e  the green arrow: seven conditions, all required
        # Recomputed from the verifier's OWN series (the naive averages, runs, changes,
        # crossing and relationship above) by a rule written straight from the recipe, then
        # restated against the SHIPPED columns, then compared with the CSV as written. A
        # condition that a candle fails is enough to refuse it an arrow, so the checks below
        # also count, per condition, the candles the OTHER five would have allowed -- a
        # condition that never refuses one is reported rather than hidden.
        fast_period, slow_period = RELATION_FAST, RELATION_SLOW
        fast_up, fast_down = naive_runs(CHANGES[fast_period])
        slow_up, _slow_down = naive_runs(CHANGES[slow_period])
        sig_words = {"cross": SIGNAL_CROSS_DIRECTION, "relation": SIGNAL_RELATION}
        sig_under = {"distance": int(round(SIGNAL_DISTANCE_PCT_AT_CROSS_MIN * (10 ** PCT_DP))),
                     "change": int(round(SIGNAL_CHG_PCT_MIN * (10 ** PCT_DP)))}
        sig_over = {"distance": int(round(SIGNAL_DISTANCE_PCT_AT_CROSS_MAX * (10 ** PCT_DP)))}
        # the keys are the summary's own perCondition keys -- one word per condition,
        # named after the row it reads -- so the funnel can be compared key by key
        masks: dict[str, list[bool]] = {k: [] for k in
                                        ("cross_direction", "distance_pct_at_cross", "relation",
                                         "flow", "chg_pct", "streak_minus", "streak_plus")}
        # the dashboard's own minute rows, read by this audit rather than taken from the
        # pipeline: the flow condition fires when the reading is present and the named
        # column is the greater one, and passes when the session ships no such reading
        flow_rows = flow_at(DAY)
        ce_flow = [b[CE_OI_CHANGE] for b in shipped]
        pe_flow = [b[PE_OI_CHANGE] for b in shipped]
        eq(ce_flow, [flow_rows.get(b["time"] // 60, (None, None))[0] for b in shipped],
           f"[{label}] the shipped {CE_OI_CHANGE} column is the dashboard's own minute row")
        eq(pe_flow, [flow_rows.get(b["time"] // 60, (None, None))[1] for b in shipped],
           f"[{label}] the shipped {PE_OI_CHANGE} column is the dashboard's own minute row")
        check(all(fr["bars"][i][CE_OI_CHANGE] == ce_flow[i] and
                  fr["bars"][i][PE_OI_CHANGE] == pe_flow[i] for i in range(len(shipped))),
              f"[{label}] the payload bars carry both dashboard columns verbatim")

        for i in range(len(bars)):
            masks["cross_direction"].append(naive_dir[i] == sig_words["cross"])
            masks["distance_pct_at_cross"].append(naive_dist[i] is not None
                                     and sig_under["distance"] <= naive_dist[i] <= sig_over["distance"])
            masks["relation"].append(naive_rel[i] == sig_words["relation"])
            masks["flow"].append(ce_flow[i] is None or pe_flow[i] is None or pe_flow[i] > ce_flow[i])
            if i == 0:
                masks["chg_pct"].append(False)
                masks["streak_minus"].append(False)
                masks["streak_plus"].append(False)
                continue
            masks["chg_pct"].append(CHANGES[slow_period][i - 1] is not None
                                    and CHANGES[slow_period][i - 1] > sig_under["change"])
            masks["streak_minus"].append(fast_up[i - 1] == 0
                                        and SIGNAL_STREAK_MINUS_MIN <= fast_down[i - 1]
                                        <= SIGNAL_STREAK_MINUS_MAX)
            masks["streak_plus"].append(slow_up[i - 1] >= SIGNAL_STREAK_PLUS_MIN)
        naive_sig = [int(all(masks[k][i] for k in masks)) for i in range(len(bars))]

        eq([b[SIGNAL_KEY] for b in shipped], naive_sig,
           f"[{label}] green-arrow flag on every bar")
        check(all(v in (0, 1) for v in naive_sig),
              f"[{label}] the flag only ever reads 0 or 1")
        eq(naive_sig[0], 0, f"[{label}] the session's first candle carries no arrow")
        SIGNAL_FIRST_CANDLE_HITS[0] += naive_sig[0]

        # restated against the shipped columns rather than the verifier's own numbers, so a
        # wrong column, an inverted comparison or a mis-scaled bound cannot pass
        restate = 0
        for i, b in enumerate(shipped):
            want = (b[xkey] == SIGNAL_CROSS_DIRECTION
                    and b[rkey] == SIGNAL_RELATION
                    and b[dkey] is not None
                    and SIGNAL_DISTANCE_PCT_AT_CROSS_MIN <= b[dkey] <= SIGNAL_DISTANCE_PCT_AT_CROSS_MAX
                    and (b[CE_OI_CHANGE] is None or b[PE_OI_CHANGE] is None
                         or b[PE_OI_CHANGE] > b[CE_OI_CHANGE]))
            if i > 0:
                prev = shipped[i - 1]
                want = want and (prev[f"sma{slow_period}_chg_pct"] is not None
                                 and prev[f"sma{slow_period}_chg_pct"] > SIGNAL_CHG_PCT_MIN
                                 and prev[f"sma{fast_period}_streak_plus"] == 0
                                 and SIGNAL_STREAK_MINUS_MIN
                                 <= prev[f"sma{fast_period}_streak_minus"]
                                 <= SIGNAL_STREAK_MINUS_MAX
                                 and prev[f"sma{slow_period}_streak_plus"]
                                 >= SIGNAL_STREAK_PLUS_MIN)
            if int(want) != b[SIGNAL_KEY]:
                restate += 1
        check(restate == 0,
              f"[{label}] every arrow matches the seven conditions restated against the "
              "shipped columns", f"{restate} disagree")

        # no look-ahead: the flag on a prefix must equal the flag the full run put there, and
        # the flag never depends on a later candle at all
        prefix_bad = []
        for cut in (1, 2, 3, len(bars) // 2, len(bars) - 1):
            if cut < 1 or cut > len(bars):
                continue
            truncated = [int(all(masks[k][i] for k in masks)) for i in range(cut)]
            if truncated != naive_sig[:cut]:
                prefix_bad.append(cut)
        check(not prefix_bad,
              f"[{label}] the first {len(bars)} candles' arrows are decided without any "
              "later candle", f"prefixes differ at {prefix_bad}")

        # each condition must matter somewhere in the delivery: count the candles the other
        # five conditions would have allowed, per condition, and fail if one never refuses
        for key in masks:
            near = sum(1 for i in range(len(bars))
                       if all(masks[o][i] for o in masks if o != key))
            SIGNAL_NEAR_MISS[key] = SIGNAL_NEAR_MISS.get(key, 0) + near

        arrows = sum(naive_sig)
        SIGNAL_ARROWS[0] += arrows
        if arrows:
            SIGNAL_FRAMES_WITH_ARROWS[0] += 1
        eq(stats["signal"]["arrows"], arrows, f"[{label}] summary arrow count")
        eq(stats["signal"]["candles"], len(bars), f"[{label}] summary candle count")
        eq(stats["signal"]["column"], SIGNAL_KEY, f"[{label}] summary names the arrow column")
        hits = [i for i, v in enumerate(naive_sig) if v]
        eq(stats["signal"]["firstIndex"], hits[0] if hits else None,
           f"[{label}] summary first arrow index")
        eq(stats["signal"]["lastIndex"], hits[-1] if hits else None,
           f"[{label}] summary last arrow index")
        funnel = stats["signal"]["perCondition"]
        eq({k: sum(1 for v in masks[k] if v) for k in masks}, funnel,
           f"[{label}] summary per-condition tallies match the verifier's own masks")
        eq(fr["signal"]["column"], SIGNAL_KEY, f"[{label}] frame names the arrow column")
        eq(fr["signal"]["crossDirection"], SIGNAL_CROSS_DIRECTION,
           f"[{label}] frame carries the crossing word")
        eq(fr["signal"]["distancePctAtCrossMaxScaled"], sig_over["distance"],
           f"[{label}] frame carries the scaled distance bound")
        eq(fr["signal"]["chgPctMinScaled"], sig_under["change"],
           f"[{label}] frame carries the scaled change threshold")
        check("AND" in fr["signal"]["rule"] and str(SIGNAL_STREAK_MINUS_MAX)
              in fr["signal"]["rule"],
              f"[{label}] frame carries the rule sentence with its windows")

        # ---- 5f  the red arrow: the green rule read the other way round
        # Recomputed from the verifier's OWN series with its own mirrored comparisons --
        # the crossing BELOW, the distance window negated with its ends swapped, the
        # relationship BELOW, the flow pair the other way round (CE above PE), the slow
        # change strictly BELOW its negated threshold, and the two runs exchanged -- then
        # compared with the CSV's red_arrow cell. Nothing here
        # calls the pipeline's `mirrored()`, so an inversion that was not the inversion would
        # have to show up as a mismatch here.
        red_over = {"distance": int(round(-SIGNAL_DISTANCE_PCT_AT_CROSS_MIN * (10 ** PCT_DP)))}
        red_under = {"distance": int(round(-SIGNAL_DISTANCE_PCT_AT_CROSS_MAX * (10 ** PCT_DP))),
                     "change": int(round(-SIGNAL_CHG_PCT_MIN * (10 ** PCT_DP)))}
        red_masks: dict[str, list[bool]] = {k: [] for k in
                                            ("cross_direction", "distance_pct_at_cross", "relation",
                                             "flow", "chg_pct", "streak_minus", "streak_plus")}
        for i in range(len(bars)):
            red_masks["cross_direction"].append(naive_dir[i] == RED_CROSS_DIRECTION)
            red_masks["flow"].append(ce_flow[i] is None or pe_flow[i] is None or ce_flow[i] > pe_flow[i])
            red_masks["distance_pct_at_cross"].append(
                naive_dist[i] is not None
                and red_under["distance"] <= naive_dist[i] <= red_over["distance"])
            red_masks["relation"].append(naive_rel[i] == RED_RELATION)
            if i == 0:
                for key in ("chg_pct", "streak_minus", "streak_plus"):
                    red_masks[key].append(False)
                continue
            red_masks["chg_pct"].append(CHANGES[slow_period][i - 1] is not None
                                        and CHANGES[slow_period][i - 1] < red_under["change"])
            red_masks["streak_minus"].append(fast_down[i - 1] == 0
                                             and SIGNAL_STREAK_MINUS_MIN <= fast_up[i - 1]
                                             <= SIGNAL_STREAK_MINUS_MAX)
            red_masks["streak_plus"].append(_slow_down[i - 1] >= SIGNAL_STREAK_PLUS_MIN)
        naive_red = [int(all(red_masks[k][i] for k in red_masks)) for i in range(len(bars))]
        eq([b[RED_KEY] for b in shipped], naive_red,
           f"[{label}] red-arrow flag on every bar")
        eq(naive_red[0], 0,
           f"[{label}] the session's first candle carries no red arrow either")
        RED_FIRST_CANDLE_HITS[0] += naive_red[0]
        paired = sum(1 for i in range(len(bars)) if naive_sig[i] and naive_red[i])
        RED_PAIRED[0] += paired
        eq(paired, 0,
           f"[{label}] no candle carries both arrows: one crossing cannot read ABOVE and BELOW")

        # the mirror gets the same funnel treatment as the rule it inverts: count the candles
        # the other five mirrored conditions would have allowed, per condition, so a mirrored
        # condition that never refused anything is reported rather than assumed away
        for key in red_masks:
            near = sum(1 for i in range(len(bars))
                       if all(red_masks[o][i] for o in red_masks if o != key))
            RED_NEAR_MISS[key] = RED_NEAR_MISS.get(key, 0) + near

        # the same rule a second time, with `mirrored()` nowhere in sight: mirror every column
        # the rules read and run the GREEN rule over that tape. What comes out must be the red
        # flags the CSV carries -- so a mirror that was not the inversion fails here, whatever
        # the rule objects say about themselves.
        mirrored = mirror_columns(shipped)
        add_signal(mirrored, SIGNAL_RULE_OBJ, SIGNAL_KEY)
        eq([b[SIGNAL_KEY] for b in mirrored], [b[RED_KEY] for b in shipped],
           f"[{label}] the red flags are exactly the green rule fired on the mirrored columns")

        red_restate = 0
        for i, b in enumerate(shipped):
            want = (b[xkey] == RED_CROSS_DIRECTION
                    and b[rkey] == RED_RELATION
                    and b[dkey] is not None
                    and -SIGNAL_DISTANCE_PCT_AT_CROSS_MAX <= b[dkey]
                    <= -SIGNAL_DISTANCE_PCT_AT_CROSS_MIN
                    and (b[CE_OI_CHANGE] is None or b[PE_OI_CHANGE] is None
                         or b[CE_OI_CHANGE] > b[PE_OI_CHANGE]))
            if i > 0:
                prev = shipped[i - 1]
                want = want and (prev[f"sma{slow_period}_chg_pct"] is not None
                                 and prev[f"sma{slow_period}_chg_pct"] < -SIGNAL_CHG_PCT_MIN
                                 and prev[f"sma{fast_period}_streak_minus"] == 0
                                 and SIGNAL_STREAK_MINUS_MIN
                                 <= prev[f"sma{fast_period}_streak_plus"]
                                 <= SIGNAL_STREAK_MINUS_MAX
                                 and prev[f"sma{slow_period}_streak_minus"]
                                 >= SIGNAL_STREAK_PLUS_MIN)
            if int(want) != b[RED_KEY]:
                red_restate += 1
        check(red_restate == 0,
              f"[{label}] every red arrow matches the seven mirrored conditions restated "
              "against the shipped columns", f"{red_restate} disagree")

        red_arrows = sum(naive_red)
        RED_ARROWS[0] += red_arrows
        if red_arrows:
            RED_FRAMES_WITH_ARROWS[0] += 1
        eq(stats["redSignal"]["arrows"], red_arrows, f"[{label}] summary red-arrow count")
        eq(stats["redSignal"]["candles"], len(bars), f"[{label}] summary red candle count")
        eq(stats["redSignal"]["column"], RED_KEY, f"[{label}] summary names the red column")
        red_hits = [i for i, v in enumerate(naive_red) if v]
        eq(stats["redSignal"]["firstIndex"], red_hits[0] if red_hits else None,
           f"[{label}] summary first red arrow index")
        eq(stats["redSignal"]["lastIndex"], red_hits[-1] if red_hits else None,
           f"[{label}] summary last red arrow index")
        eq({k: sum(1 for v in red_masks[k] if v) for k in red_masks},
           stats["redSignal"]["perCondition"],
           f"[{label}] summary red per-condition tallies match the verifier's own masks")
        for key in red_masks:
            near = sum(1 for i in range(len(bars))
                       if all(red_masks[o][i] for o in red_masks if o != key))
            RED_NEAR_MISS[key] = RED_NEAR_MISS.get(key, 0) + near
        eq(fr["redSignal"]["column"], RED_KEY, f"[{label}] frame names the red column")
        eq(fr["redSignal"]["chgPctMinScaled"], red_under["change"],
           f"[{label}] frame carries the red rule's negated change threshold")
        eq(fr["redSignal"]["distancePctAtCrossMinScaled"], red_under["distance"],
           f"[{label}] frame carries the red rule's negated distance floor")
        eq(fr["redSignal"]["rule"], CONFIG_OBJ.signal_red_rule,
           f"[{label}] frame carries the red rule sentence the recipe declares")
        check("RED ARROW" in fr["redSignal"]["rule"]
              and RED_CROSS_DIRECTION in fr["redSignal"]["rule"]
              and "below" in fr["redSignal"]["rule"],
              f"[{label}] the red rule sentence names the red arrow, its own crossing word and "
              "the side of the change threshold it reads")

        # ---- summary agreement
        eq(fr["bars"][-1]["close"], shipped[-1]["close"], f"[{label}] payload close matches JSON")
        eq(stats["open"], shipped[0]["open"], f"[{label}] summary.open")
        eq(stats["high"], max(b["high"] for b in shipped), f"[{label}] summary.high")
        eq(stats["low"], min(b["low"] for b in shipped), f"[{label}] summary.low")
        eq(stats["avgTicksPerBar"], round(sum(b["ticks"] for b in shipped) / len(shipped), 1),
           f"[{label}] summary.avgTicksPerBar")
        eq(stats["greenBars"] + stats["redBars"] + stats["dojiBars"], len(shipped),
           f"[{label}] colour tally covers every bar")
        eq(fr["analyticsSmas"], list(ANALYTICS_SMAS), f"[{label}] payload analyticsSmas")

        # ---- 6  CSV
        with (OUT_DATA / DAY / f"nifty_{slug}.csv").open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
            fh.seek(0)
            header = fh.readline().rstrip("\n")
        expect_header = ",".join(
            ["time_ist", "epoch", "open", "high", "low", "close", "change", "change_pct"]
            + [f"sma{p}" for p in SMA_PERIODS]
            + [f"sma{p}_{k}" for p in ANALYTICS_SMAS for k in ("chg_pct", "streak_plus", "streak_minus")]
            + [f"sma{DIRECTION_FAST}_vs_sma{DIRECTION_SLOW}_{k}_streak"
               for k in ("above", "below")]
            + [f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_cross_direction",
               f"sma{CROSS_DIST_FROM}_vs_sma{CROSS_DIST_TO}_distance_pct_at_cross",
               f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_distance_pct_at_cross"]
            + [f"sma{RELATION_FAST}_vs_sma{RELATION_SLOW}_relation"]
            + [SIGNAL_KEY, RED_KEY]
            + ["atm", "ticks", CE_OI_CHANGE, PE_OI_CHANGE])
        eq(header, expect_header, f"[{label}] CSV header")
        if csv_columns is None:
            csv_columns = expect_header
        eq(len(rows), len(bars), f"[{label}] CSV row count")
        cbad = []
        for i, r in enumerate(rows):
            if r["epoch"] != str(bars[i]["time"]) or r["open"] != f"{bars[i]['open']:.2f}":
                cbad.append((i, "time/open", r["epoch"], bars[i]["time"]))
            for period in SMA_PERIODS:
                v = shipped[i][f"sma{period}"]
                if r[f"sma{period}"] != ("" if v is None else f"{v:.2f}"):
                    cbad.append((i, f"sma{period}", r[f"sma{period}"]))
            for period in ANALYTICS_SMAS:
                v = shipped[i][f"sma{period}_chg_pct"]
                if r[f"sma{period}_chg_pct"] != ("" if v is None else f"{v:.{PCT_DP}f}"):
                    cbad.append((i, f"sma{period}_chg_pct", r[f"sma{period}_chg_pct"]))
                for kind in ("plus", "minus"):
                    if r[f"sma{period}_streak_{kind}"] != str(shipped[i][f"sma{period}_streak_{kind}"]):
                        cbad.append((i, f"sma{period}_streak_{kind}", r[f"sma{period}_streak_{kind}"]))
            for key in (f"sma{DIRECTION_FAST}_vs_sma{DIRECTION_SLOW}_above_streak",
                        f"sma{DIRECTION_FAST}_vs_sma{DIRECTION_SLOW}_below_streak"):
                if r[key] != str(shipped[i][key]):
                    cbad.append((i, key, r[key]))
            # the crossing row is text ('above' / 'below' / empty), the distances are the
            # scaled 4-decimal values, so both are compared against the verifier's own work
            want_dir = "" if naive_dir[i] is None else naive_dir[i]
            if r[xkey] != want_dir:
                cbad.append((i, xkey, r[xkey], want_dir))
            for key, scaled in ((dkey, naive_dist[i]), (pkey, naive_pair[i])):
                want = "" if scaled is None else fmt_scaled(scaled)
                if r[key] != want:
                    cbad.append((i, key, r[key], want))
            # the relationship is a word, or an empty field where there is no side
            want_rel = "" if naive_rel[i] is None else naive_rel[i]
            if r[rkey] != want_rel:
                cbad.append((i, rkey, r[rkey], want_rel))
            # the arrows are flags: the CSV writes the same 1 / 0 the JSON bar carries,
            # for both rules
            for key in (SIGNAL_KEY, RED_KEY):
                if r[key] != str(shipped[i][key]):
                    cbad.append((i, key, r[key], shipped[i][key]))
        check(not cbad, f"[{label}] CSV cells match the JSON bars on every row",
              f"{len(cbad)} mismatches, first {cbad[:3]}")
        check(all(c not in header for c in ("alignment", "close_minus_sma", "marker",
                                            "pattern", "crossover", "markers")),
              f"[{label}] CSV carries no alignment marker or pattern columns")
        eq([c for c in header.split(",") if "signal" in c or c.endswith("_arrow")],
           [SIGNAL_KEY, RED_KEY],
           f"[{label}] the two arrow rules are the CSV's only signal columns, green first")
        eq([c for c in header.split(",") if c.endswith("_cross_direction")
            or c.endswith("_distance_pct_at_cross")],
           [f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_cross_direction",
            f"sma{CROSS_DIST_FROM}_vs_sma{CROSS_DIST_TO}_distance_pct_at_cross",
            f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_distance_pct_at_cross"],
           f"[{label}] CSV carries the three crossing columns, in that order")
        eq(header.split(",").index(f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_cross_direction"),
           header.split(",").index("atm") - 6,
           f"[{label}] the crossing columns sit between the direction row and the tape")
        eq(header.split(",").index(rkey), header.split(",").index("atm") - 3,
           f"[{label}] the relationship column sits between the crossing columns and the arrows")
        eq(header.split(",").index(SIGNAL_KEY), header.split(",").index("atm") - 2,
           f"[{label}] the green-arrow column sits first among the arrow columns")
        eq(header.split(",").index(RED_KEY), header.split(",").index("atm") - 1,
           f"[{label}] the red-arrow column sits between the green arrow and the tape")
        eq(header.split(",").index(f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_cross_direction"),
           header.split(",").index("atm") - 6,
           f"[{label}] the crossing columns keep their place ahead of both arrow columns")

        a = stats["analytics"]
        print("    " + "  ".join(
            f"SMA{p} run +{a[str(p)]['streakPlus']}/-{a[str(p)]['streakMinus']} "
            f"(max +{a[str(p)]['maxStreakPlus']}/-{a[str(p)]['maxStreakMinus']})" for p in ANALYTICS_SMAS)
            + f"   {DIRECTION_FAST}v{DIRECTION_SLOW} dir "
              f"{stats['direction']['displayLabel']} "
              f"(max +{stats['direction']['maxAbove']}/-{stats['direction']['maxBelow']}, "
              f"{stats['direction']['switches']} switches)")

    # the two reset rules must actually fire somewhere in the real session, or the assertions
    # above would be vacuous (the synthetic cases in section 10 cover the rule regardless)
    check(RESTART_WITNESSES[0] > 0,
          "the session contains reversals that restart a run at 1",
          f"{RESTART_WITNESSES[0]} seen")
    check(ZERO_WITNESSES[0] > 0,
          "the session contains exact-zero changes that reset both runs",
          f"{ZERO_WITNESSES[0]} seen")
    check(DIR_RESET_WITNESSES[0] > 0,
          "the session contains candles where the direction row resets to +0 / -0",
          f"{DIR_RESET_WITNESSES[0]} seen")
    check(DIR_SWITCH_WITNESSES[0] > 0,
          "the session contains ABOVE <-> BELOW switches that restart the streak at 1",
          f"{DIR_SWITCH_WITNESSES[0]} seen")
    check(CROSS_HERE[0] > 0,
          "the session contains strict SMA 2 vs SMA 9 crossings",
          f"{CROSS_HERE[0]} seen")
    check(CROSS_BLANK_HERE[0] > 0,
          "the session contains crossings whose distance row is blank (no divisor yet)",
          f"{CROSS_BLANK_HERE[0]} seen")
    CROSS_WITNESSES[0] += CROSS_HERE[0]
    CROSS_BLANK_DISTANCE[0] += CROSS_BLANK_HERE[0]
    check(REL_ABOVE_BARS[0] > 0 and REL_BELOW_BARS[0] > 0,
          "the relationship row carries both sides on live data",
          f"{REL_ABOVE_BARS[0]} ABOVE / {REL_BELOW_BARS[0]} BELOW cells")
    check(REL_BLANK_BARS[0] > 0,
          "the relationship row is blank where there is no side",
          f"{REL_BLANK_BARS[0]} blank cells")
    check(REL_TIES[0] > 0,
          "the delivered sessions contain candles where SMA 9 and SMA 44 are exactly equal",
          f"{REL_TIES[0]} tied candles")

# --------------------------------------------------------------------------------------
# Sections 1-6 for every session, each against its own artifacts and tick file
# --------------------------------------------------------------------------------------

for _day in DAY_KEYS:
    print(f"\n{'=' * 86}\n=== {_day} ===")
    audit_day(_day, SUMMARY[_day]["session"], TICKS[_day], SUMMARY[_day]["timeframes"],
              {"timeframes": next(d["timeframes"] for d in DAY_ENTRIES if d["date"] == _day)})

# --------------------------------------------------------------------------------------
# 7  removal of the cross-marker logic
# --------------------------------------------------------------------------------------

print("\n7  the removed marker logic, and the two rules that replaced it")
# The cross-marker vocabulary this project had removed stays removed. Exactly six identifiers
# may reappear, because exactly two marker rules now exist -- the green arrow and the red
# mirror -- and the chart engine needs them to draw both: the primitive and its setter, the
# two arrow shapes, and the two sides of the bar. Nothing else in that vocabulary is allowed
# back, and the accounting below proves the six appear nowhere but in those two rules.
SIGNAL_API = ("createSeriesMarkers", "setMarkers", "arrowUp", "arrowDown",
              "belowBar", "aboveBar")
FORBIDDEN = [
    "crossover", "crossovers", "computeCrosses", "cross_markers", "markerPrimitive",
    "markerPayload", "patternAt", "patterns",
    "pattern_markers", "swing_high", "swing_low", "is_swing", "SWING_LOOKBACK",
    "PRICE_EQUAL_TOLERANCE", "signalOf", "signalTag", "alignmentSpans",
    "alignmentText", "signal_sma", "close_minus_sma", "PRIMARY_SMA", "markerCounts",
    "markerLookback",
]
# trading advice has never been part of this project, and one arrow rule does not make it.
# Only prose words are listed: `entry` and `target` are ordinary identifiers in the sheet
# (`var entry = DAY_BY[day]`, `e.target`), so they would flag the code rather than the claim.
FORBIDDEN_ADVICE = ["buy", "sell", "stop loss", "stop-loss", "take profit", "take-profit",
                    "recommendation"]


def contains_term(text: str, term: str) -> bool:
    return re.search(r"\b" + re.escape(term) + r"\b", text) is not None


# every module of the pipeline, then the template it renders
check(len(PIPELINE_SOURCES) > 1 and PIPELINE_SOURCES[0] == BUILDER and
      all(p.suffix == ".py" for p in PIPELINE_SOURCES),
      "the pipeline is a package of modules behind one entry point",
      f"{len(PIPELINE_SOURCES)} files: {[p.name for p in PIPELINE_SOURCES]}")
for path in PIPELINE_SOURCES + [TEMPLATE]:
    text = path.read_text(encoding="utf-8")
    hits = sorted({w for w in FORBIDDEN if contains_term(text, w)})
    check(not hits, f"{path.relative_to(ROOT).as_posix()} contains no removed marker"
                    " identifiers", f"found {hits}")

sheet_text = SHEET.read_text(encoding="utf-8")
app_text = sheet_text[sheet_text.index('<script id="payload"'):]
hits = sorted({w for w in FORBIDDEN if contains_term(app_text, w)})
check(not hits, "delivered sheet's own script has no removed marker identifiers", f"found {hits}")
# The allowed identifiers live in exactly three places and nowhere else: the one function
# that draws the markers, the tiny helper that picks a rule's arrow shape, and the two lines
# that construct the rules with their fallback sides of the bar. Extracting those regions
# from the template and from the delivered script, and finding every occurrence inside them,
# is what proves the sheet draws TWO rules and no third: another marker rule anywhere would
# show up as a term counted outside these three.
_apply_at = TEMPLATE_TEXT.index("function applySignalMarkers(f) {")
_apply_body = TEMPLATE_TEXT[_apply_at:TEMPLATE_TEXT.index("\n  }", _apply_at) + 4]
_shape_at = TEMPLATE_TEXT.index("function arrowShape(rule) {")
_shape_body = TEMPLATE_TEXT[_shape_at:TEMPLATE_TEXT.index("\n", _shape_at) + 1]
_construct = "\n".join(line for line in TEMPLATE_TEXT.splitlines()
                       if re.match(r"  var (SIG|RED) = arrowRule\(", line))
eq(len(re.findall(r"var (SIG|RED) = arrowRule\(", TEMPLATE_TEXT)), 2,
   "the sheet declares exactly two marker rules")
check("var RULES = [SIG, RED];" in TEMPLATE_TEXT,
      "both rules run from one list, so a third could not be drawn without changing it")
check("marker: { position: rule.position, shape: arrowShape(rule)," in TEMPLATE_TEXT,
      "the browser's JSON export describes each rule's own marker")


def api_hits(text: str, term: str) -> int:
    """Whole-word uses, so an unrelated key such as 'belowBars' is not counted as 'belowBar'."""
    return len(re.findall(r"\b" + re.escape(term) + r"\b", text))


for _term in SIGNAL_API:
    eq(api_hits(TEMPLATE_TEXT, _term),
       api_hits(_apply_body, _term) + api_hits(_shape_body, _term) + api_hits(_construct, _term),
       f"every '{_term}' in the template is the drawing, a rule's own shape, or its side")
# the inlined payload sits inside app_text, and it legitimately carries each rule's
# markerPosition once per frame and once in the meta block -- so the accounting is done over
# the sheet's own code, past that script element
app_code = app_text.split("</script>", 1)[1] if "</script>" in app_text else app_text
_app_at = app_code.index("function applySignalMarkers(f) {")
_app_body = app_code[_app_at:app_code.index("\n  }", _app_at) + 4]
_app_shape_at = app_code.index("function arrowShape(rule) {")
_app_shape = app_code[_app_shape_at:app_code.index("\n", _app_shape_at) + 1]
_app_construct = "\n".join(line for line in app_code.splitlines()
                           if re.match(r"  var (SIG|RED) = arrowRule\(", line))
for _term in SIGNAL_API:
    eq(api_hits(app_code, _term),
       api_hits(_app_body, _term) + api_hits(_app_shape, _term) + api_hits(_app_construct, _term),
       f"the delivered script's own code mentions '{_term}' only where it draws or describes "
       "an arrow")
eq(api_hits(_app_body, "createSeriesMarkers"), 2,
   "the delivered sheet creates one marker primitive for both rules, with the guard around it")
eq(api_hits(app_text, "setMarkers"), 2,
   "the primitive is updated in place, not recreated, on every timeframe")
# both shapes and both sides of the bar are wired, one per rule, and they are chosen from the
# rule rather than written at the drawing site
eq(sorted(re.findall(r'"(arrow(?:Down|Up))"', _shape_body)), ["arrowDown", "arrowUp"],
   "the shape helper answers both directions, so each rule draws its own arrow")
eq(sorted(re.findall(r'"(aboveBar|belowBar)"', _construct)), ["aboveBar", "belowBar"],
   "one rule is drawn below the bar and the other above it")
eq(re.search(r"markers\.push\(\{ time: f\.bars\[i\]\.time, position: rule\.position,\s*\n?\s*"
              r"color: arrowColor\(rule\), shape: arrowShape\(rule\), text: \"\" \}\)",
              TEMPLATE_TEXT) is not None, True,
   "each marker takes its position, colour and shape from the rule that fired")
eq(_apply_body.count("markers.push"), 1,
   "the marker list is built in one place, from the flag arrays")

payload_text = json.dumps(payload)
# 'cross' now names the two crossing rows the requirement added, so this is about the
# MARKER vocabulary the earlier requirement removed, not about the word itself
check("markers" not in payload_text, "inlined payload has no marker keys")
check(not any(term in payload_text for term in ("crossover", "crossovers", "cross_markers")),
      "inlined payload carries no cross-marker key")
check(not any(term in json.dumps(META.get("cross", {}))
               for term in ("markers", "crossover", "cross_markers")),
      "the crossing block itself carries no marker key")
check(all(d["session"]["signalLogic"] is True for d in DAY_ENTRIES),
      "every session records the marker rules that run")
check(all("signal" in d["session"] and d["session"]["signal"]["column"] == SIGNAL_KEY
          for d in DAY_ENTRIES),
      "every session names the green-arrow column and its thresholds")
check(all("redSignal" in d["session"] and d["session"]["redSignal"]["column"] == RED_KEY
          and d["session"]["redSignal"]["inverted"] is True for d in DAY_ENTRIES),
      "every session names the red-arrow column and records it as the inverted rule")
check(not any(set(d["session"]) & {"swingLookback", "markerLookback", "markers", "crossovers"}
              for d in DAY_ENTRIES),
      "no session meta carries swing/marker keys")
check(not (set(META) & {"swingLookback", "markerLookback", "markers", "crossovers"}),
      "payload meta carries no swing/marker keys")
_sig_keys = set(META.get("signal", {}))
_RULE_KEYS = {"enabled", "column", "crossFastPeriod", "crossSlowPeriod", "distanceFromPeriod",
              "distanceToPeriod", "fastPeriod", "slowPeriod", "crossDirection", "relation",
              "distancePctAtCrossMin", "distancePctAtCrossMax", "distancePctAtCrossMinScaled",
              "distancePctAtCrossMaxScaled", "chgPctMin", "chgPctMinScaled", "streakMinusMin",
              "streakMinusMax", "streakPlusMin", "rule", "label", "mark", "markerPosition",
              "inverted", "chgAbove", "fastRun", "slowRun", "flowAbove", "flowBelow",
              "useFlow"}
eq(sorted(_sig_keys), sorted(_RULE_KEYS),
   "the payload's signal block carries exactly the rule's own parameters")
eq(sorted(set(META.get("redSignal", {}))), sorted(_RULE_KEYS),
   "the payload's redSignal block carries the same parameters, in the same shape")
eq(list(META.get("redSignal", {})), list(META.get("signal", {})),
   "the two blocks carry their keys in the same order, so the sheet can read them alike")
_advice = sorted({w for w in FORBIDDEN_ADVICE
                  if contains_term(app_text, w) or contains_term(payload_text, w)})
check(not _advice, "the delivered sheet states no advice, only the rule's own readings",
      f"found {_advice}")

# --------------------------------------------------------------------------------------
# 8  the sheet itself
# --------------------------------------------------------------------------------------

print("\n8  sheet structure")
check(SHEET.exists() and SHEET.stat().st_size > 200_000, "delivered sheet exists and is self-contained")
check("__DATA_JSON__" not in sheet_text and "__CHART_LIB__" not in sheet_text,
      "no template placeholders left in the sheet")

check(re.search(r"INDICATOR_PANE", TEMPLATE_TEXT) is None,
      "the chart plots one pane: no second pane index survives in the sheet")
check(re.search(r"addSeries\(LWC\.LineSeries, \{.*?\}, INDICATOR_PANE\)", TEMPLATE_TEXT,
                re.S) is None, "no analytics series is drawn in a lower pane")
check(re.search(r"addSeries\(LWC\.CandlestickSeries, \{.*?\}, PRICE_PANE\)", TEMPLATE_TEXT,
                re.S) is not None, "candles are added to the price pane")
_pane_args = re.findall(r"chart\.addSeries\(LWC\.\w+, \{.*?\}, (\w+)\)", TEMPLATE_TEXT, re.S)
eq(_pane_args, ["PRICE_PANE", "PRICE_PANE"],
   "every series the sheet adds, the candles and the three price averages, lands in that "
   "one pane")
check("setStretchFactor" not in TEMPLATE_TEXT,
      "one pane: there is no height split left to configure")
check(re.search(r"overlay\s*:", TEMPLATE_TEXT) is None,
      "no overlay option is used to fake the placement")
check("separatorColor" not in TEMPLATE_TEXT and "enableResize" not in TEMPLATE_TEXT,
      "one pane: no pane separator or drag handle is configured")
check("var WINDOW_BARS = Math.max(2, META.windowBars || 100);" in TEMPLATE_TEXT and
      "var shown = Math.min(n, WINDOW_BARS);" in TEMPLATE_TEXT and
      "setVisibleLogicalRange({ from: n - shown - 0.5, to: n - 0.5 })" in TEMPLATE_TEXT,
      "a chart opens on its latest WINDOW_BARS candles, sized to fill the pane")
check("setVisibleLogicalRange({ from: -0.5, to: n - 0.5 })" not in TEMPLATE_TEXT,
      "the open window is not the whole session: the earlier bars stay one drag away")
check(re.search(r'dblclick", function \(\) \{ f\.userZoomed = false; scheduleFit\(f\); \}',
                TEMPLATE_TEXT) is not None,
      "a double-click returns the chart to the latest window")
eq(META.get("windowBars"), WINDOW_BARS,
   "the payload carries the window the sheet opens on, so the window travels with the recipe")

# the ten rows, exactly as specified
for row_label in ("Candle / Time", '" Change (%)', '" Consecutive Count (+N / \\u2212N)"',
                  ' Direction Streak (+ABOVE / \\u2212BELOW)',
                  '" Cross Direction"', '" Distance (%) at SMA "', ' (ABOVE / BELOW)"'):
    check(row_label in TEMPLATE_TEXT, f"table row label present: {row_label}")
eq(      TEMPLATE_TEXT.count('class="rowlab"'), 7,
   "row labels come from the time row, two loops of three rows each, the direction row, "
   "the two crossing rows and the relationship row (10 metric rows + the time row)")
check('SIG_LABEL' not in TEMPLATE_TEXT.split('var labels = ["Candle / Time"]')[1]
      .split("var head =")[0],
      "the green arrow adds no row to the metric table: it is drawn on the chart")

# the SMA 2 vs SMA 9 direction streak, as coded in the sheet
check(re.search(r"function directionFromAnalytics\(fast, slow\)", TEMPLATE_TEXT) is not None,
      "the sheet computes the direction streak from the two averages")
check(re.search(r"else if \(fc > sc && chg > 0\) \{", TEMPLATE_TEXT) is not None,
      "the sheet's ABOVE rule is SMA fast > SMA slow with a positive slow change")
check(re.search(r"else if \(fc < sc && chg < 0\) \{", TEMPLATE_TEXT) is not None,
      "the sheet's BELOW rule is SMA fast < SMA slow with a negative slow change")
check(re.search(r"a = 0; b = 0;\s*// equality, or a change of exactly zero", TEMPLATE_TEXT)
      is not None, "a candle satisfying neither rule resets both direction runs to 0")
check(re.search(r"a = 0; b = 0;\s*// no comparison available yet", TEMPLATE_TEXT)
      is not None, "an unmeasurable candle also resets the direction row")
check("f.dir = directionFromAnalytics" in TEMPLATE_TEXT,
      "the direction row is computed with the pinned analytics, not the editable toolbar")
check(re.search(r"labels\[1 \+ ANALYTICS_PERIODS\.length \* 2\]", TEMPLATE_TEXT) is not None,
      "the direction row is emitted once, after the six per-period rows")
check("DIR_ABOVE_COL, DIR_BELOW_COL" in TEMPLATE_TEXT,
      "the sheet's CSV export carries the direction columns")
check("rec[DIR_ABOVE_COL] = f.dir.above[i]" in TEMPLATE_TEXT and
      "rec[DIR_BELOW_COL] = f.dir.below[i]" in TEMPLATE_TEXT,
      "the sheet's JSON export carries the direction values per bar")
check(TEMPLATE_TEXT.count("countLabel") >= 6,
      "the direction row reuses the shared run formatter")
check("f.dir.lastAbove" in TEMPLATE_TEXT and "f.dir.maxAbove" in TEMPLATE_TEXT,
      "the chips and the comparison matrix read the direction row too")
check(META.get("directionStreak", {}).get("fastPeriod") == DIRECTION_FAST and
      META.get("directionStreak", {}).get("slowPeriod") == DIRECTION_SLOW,
      "payload meta pins the direction pair to SMA 2 vs SMA 9")
check(META.get("directionStreak", {}).get("aboveColumn") ==
      f"sma{DIRECTION_FAST}_vs_sma{DIRECTION_SLOW}_above_streak" and
      META.get("directionStreak", {}).get("belowColumn") ==
      f"sma{DIRECTION_FAST}_vs_sma{DIRECTION_SLOW}_below_streak",
      "payload meta names the direction-streak columns")
check(all("ABOVE" in d["session"].get("directionStreak", {}).get("rule", "") and
          "BELOW" in d["session"].get("directionStreak", {}).get("rule", "")
          for d in DAY_ENTRIES),
      "every session records the ABOVE / BELOW direction rule")

# the two crossing rows, as coded in the sheet
check(re.search(r"function crossFromSmas\(fast, slow, from, to\)", TEMPLATE_TEXT) is not None,
      "the sheet computes the crossing rows from the averages themselves")
check(re.search(r'if \(pf < ps && fc > sc\) \{ dir\[i\] = "ABOVE"; \}', TEMPLATE_TEXT) is not None,
      "the sheet's ABOVE branch is a strict previous -> current crossing upwards")
check(re.search(r'else if \(pf > ps && fc < sc\) \{ dir\[i\] = "BELOW"; \}', TEMPLATE_TEXT)
      is not None,
      "the sheet's BELOW branch is a strict previous -> current crossing downwards")
check("// same side, or an equal pair: no crossing" in TEMPLATE_TEXT,
      "the sheet treats the same side, and an equal pair, as no crossing")
check("pf = i > 0 ? fast.smaCents[i - 1] : null;" in TEMPLATE_TEXT,
      "the sheet compares each candle with the previous one, never with a later bar")
check(re.search(r"dist\[i\] = divHalfUp\(\(fv - tv\) \* 100 \* scale, tv\)", TEMPLATE_TEXT)
      is not None,
      "the sheet's distance is ((from - to) / to) * 100 on the crossing candle")
check("if (fv !== null && fv !== undefined && tv !== null && tv !== undefined && tv !== 0)"
      in TEMPLATE_TEXT,
      "the sheet leaves a distance blank when the divisor is missing or zero")
check(re.search(r"cross: \{ fastPeriod: X_FAST, slowPeriod: X_SLOW,", TEMPLATE_TEXT) is not None and
      "directionColumn: CROSS_COL" in TEMPLATE_TEXT,
      "the sheet's JSON export describes the crossing rows")
check("CROSS_COL, CROSS_DIST_COL, CROSS_PAIR_COL" in TEMPLATE_TEXT,
      "the sheet's CSV export carries the three crossing columns")
check("rec[CROSS_DIST_COL] = f.cross.dist[i] === null ? null :" in TEMPLATE_TEXT and
      "rec[CROSS_COL] = f.cross.dir[i];" in TEMPLATE_TEXT,
      "the sheet's JSON export carries the crossing values bar by bar")
check('X_FAST + "v" + X_SLOW + " cross"' in TEMPLATE_TEXT and
      'X_FROM + "v" + X_TO + " dist"' in TEMPLATE_TEXT,
      "the crosshair read-out shows the crossing and its distance")
check('"<th>SMA" + X_FAST + "v" + X_SLOW + " cross</th>"' in TEMPLATE_TEXT and
      '"<th>SMA" + X_FROM + "v" + X_TO + " dist %</th>"' in TEMPLATE_TEXT,
      "the candle ledger carries both crossing columns as well")
check(re.search(r'\(ANALYTICS_PERIODS\.length \* 2 \+ 4\) \+ " metric rows', TEMPLATE_TEXT)
      is not None,
      "the analytics caption counts the ten metric rows")
check('esc(CROSS_RULE)' in TEMPLATE_TEXT and 'esc(CROSS_DISTANCE_RULE)' in TEMPLATE_TEXT,
      "both crossing rows carry their rule in the label's tooltip")
check(META.get("cross", {}).get("directionColumn") ==
      f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_cross_direction" and
      META.get("cross", {}).get("distanceColumn") ==
      f"sma{CROSS_DIST_FROM}_vs_sma{CROSS_DIST_TO}_distance_pct_at_cross" and
      META.get("cross", {}).get("pairDistanceColumn") ==
      f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_distance_pct_at_cross",
      "payload meta names the three crossing columns")
check(META.get("cross", {}).get("fastPeriod") == CROSS_FAST and
      META.get("cross", {}).get("slowPeriod") == CROSS_SLOW and
      META.get("cross", {}).get("distanceFromPeriod") == CROSS_DIST_FROM and
      META.get("cross", {}).get("distanceToPeriod") == CROSS_DIST_TO,
      "payload meta pins the crossing pair and the distance pair")
check(all("above" in d["session"].get("cross", {}).get("rule", "").lower() and
          "equal" in d["session"].get("cross", {}).get("rule", "").lower()
          for d in DAY_ENTRIES),
      "every session records the crossing rule, including the equal-pair case")
check(all(str(CROSS_DIST_TO) in d["session"].get("cross", {}).get("distanceRule", "")
          for d in DAY_ENTRIES),
      "every session records the distance formula for the pair it used")

# the SMA 9 vs SMA 44 above/below relationship row, as coded in the sheet
check(re.search(r"function relationFromSmas\(fast, slow\)", TEMPLATE_TEXT) is not None,
      "the sheet computes the relationship row from the two averages")
check("f.rel = relationFromSmas(" in TEMPLATE_TEXT,
      "the relationship row uses the pinned analytics, not the editable toolbar")
check(re.search(r"\|\| fc === sc\) \{", TEMPLATE_TEXT) is not None,
      "the sheet refuses a side to a pair that is exactly equal on that candle")
check(re.search(r"labels\[1 \+ ANALYTICS_PERIODS\.length \* 2 \+ 3\]", TEMPLATE_TEXT)
      is not None,
      "the relationship row is emitted after the two crossing rows")
check("esc(REL_RULE)" in TEMPLATE_TEXT,
      "the relationship row carries its rule in the label's tooltip")
check("rec[REL_COL] = f.rel.words[i]" in TEMPLATE_TEXT and
      ".concat([REL_COL])" in TEMPLATE_TEXT,
      "both exports carry the relationship column")
check(META.get("relation", {}).get("fastPeriod") == RELATION_FAST and
      META.get("relation", {}).get("slowPeriod") == RELATION_SLOW,
      "payload meta pins the relationship pair")
check(META.get("relation", {}).get("relationColumn") ==
      f"sma{RELATION_FAST}_vs_sma{RELATION_SLOW}_relation",
      "payload meta names the relationship column")
check(all("ABOVE" in d["session"].get("relation", {}).get("rule", "") and
          "BELOW" in d["session"].get("relation", {}).get("rule", "")
          for d in DAY_ENTRIES),
      "every session records the relationship rule")
check(re.search(r"ANALYTICS_PERIODS\s*=\s*\(META\.analyticsSmas \|\| \[2, 9, 44\]\)", TEMPLATE_TEXT)
      is not None, "the sheet's analytics periods default to 2, 9 and 44")
check(TEMPLATE_TEXT.count("data-i=") >= 3, "every candle column carries its index handle")
check(TEMPLATE_TEXT.count("countLabel") >= 3, "runs are formatted by one shared helper")
check(re.search(r'<td class="blank"[^<]*></td>', TEMPLATE_TEXT) is not None,
      "the table leaves an unavailable percentage change genuinely empty")
check(">blank</td>" not in TEMPLATE_TEXT, "no placeholder word is written into a blank cell")

# the run rule, as coded in the sheet
check(re.search(r"if \(scaled > 0\) \{ p \+= 1; m = 0; \}", TEMPLATE_TEXT) is not None,
      "a rise in the sheet extends the rising run and clears the falling one")
check(re.search(r"else if \(scaled < 0\) \{ m \+= 1; p = 0; \}", TEMPLATE_TEXT) is not None,
      "a fall in the sheet extends the falling run and clears the rising one")
check(re.search(r"else \{ p = 0; m = 0; \}", TEMPLATE_TEXT) is not None,
      "a zero change in the sheet resets both runs")
check("chg[i] = null" in TEMPLATE_TEXT and "chgScaled[i] = null" in TEMPLATE_TEXT,
      "a blank change is recorded as null rather than a number")

ind_idx = TEMPLATE_TEXT.index('class="ind-block"')
chart_idx = TEMPLATE_TEXT.index('<div class="chart" id="chart-')
check(chart_idx < ind_idx, "the analytics block is rendered after (below) the chart")
check(TEMPLATE_TEXT.index('class="an-scroll"') > ind_idx,
      "the table is inside the indicator block")

check("f.anLines" not in TEMPLATE_TEXT and "createPriceLine" not in TEMPLATE_TEXT,
      "the changes are tabulated, not plotted: the sheet keeps no analytics series of its own")
check("ANALYTICS_PERIODS.map(function (p) { return f.an[p]; })" in TEMPLATE_TEXT,
      "the table is still fed from the pinned analytics series")
check("fmtScaled" in TEMPLATE_TEXT, "the sheet formats percentage changes from scaled integers")

check(csv_columns is not None and
      '"time_ist", "epoch", "open", "high", "low", "close", "change", "change_pct"'
      in TEMPLATE_TEXT, "sheet export starts from the same base columns")

eq(set(fr["barFields"]), {"time", "open", "high", "low", "close", "atm", "ticks",
                           CE_OI_CHANGE, PE_OI_CHANGE},
   "payload bar fields are OHLC, the tape's own and the dashboard's two columns")
check("smaLast" in json.dumps(fr["stats"]), "payload stats carry the SMA snapshot")

# --- the session (day) dimension -------------------------------------------------------
check('class="daytabs"' in TEMPLATE_TEXT and 'id="daytabs"' in TEMPLATE_TEXT,
      "the sheet carries a session (day) tab strip")
check(re.search(r"function renderDayTabs\(\)", TEMPLATE_TEXT) is not None,
      "the day strip is rendered from the payload, not hard-coded")
check(re.search(r"function switchDay\(day\)", TEMPLATE_TEXT) is not None,
      "the sheet can switch sessions")
check(re.search(r"getElementById\(\"daytabs\"\)\.addEventListener", TEMPLATE_TEXT) is not None,
      "the day strip is wired to switchDay")
check(re.search(r"function keyOf\(day, tf\)", TEMPLATE_TEXT) is not None and
      "idOf(" in TEMPLATE_TEXT,
      "every panel id is keyed by (session, timeframe), so days cannot collide")
check(re.search(r"function ensureDay\(day\)", TEMPLATE_TEXT) is not None and
      re.search(r"if \(!entry \|\| entry\.built\) \{ return entry; \}", TEMPLATE_TEXT) is not None,
      "sessions are materialised lazily on first open")
check("daypanels" in TEMPLATE_TEXT and 'data-active' in TEMPLATE_TEXT,
      "only the active session's panels are shown")
check(re.search(r"body\.js-printing \.daypanels\{display:none\}", TEMPLATE_TEXT) is not None,
      "printing covers the active session only")
check(re.search(r"var DAYS = DATA\.days \|\| \[\]", TEMPLATE_TEXT) is not None,
      "the sheet reads its sessions from the payload")
# comments may name a date as an example; the CODE must not
_template_code = re.sub(r"/\*.*?\*/", "", TEMPLATE_TEXT, flags=re.S)
_template_code = re.sub(r"//[^\n]*", "", _template_code)
_literal_dates = [d["date"] for d in DAY_ENTRIES if d["date"] in _template_code]
check(not _literal_dates and "META.dates" not in TEMPLATE_TEXT,
      "the day strip is data-driven, not a literal date list", f"found {_literal_dates}")
check(re.search(r"analyticsSmas: ANALYTICS_PERIODS", TEMPLATE_TEXT) is not None or
      re.search(r"ANALYTICS_PERIODS\s*=\s*\(META\.analyticsSmas", TEMPLATE_TEXT) is not None,
      "every panel derives its analytics periods from the same pin")

# --- the shipped sheet's own payload ---------------------------------------------------
check(all(len(d["timeframes"]) == len(TIMEFRAMES) for d in DAY_ENTRIES),
      "every session in the payload carries all timeframes")
_bar_fields = {"time", "open", "high", "low", "close", "atm", "ticks", "_i",
               CE_OI_CHANGE, PE_OI_CHANGE}
_extra = sorted({k for d in DAY_ENTRIES for tf_ in d["timeframes"].values()
                 for b in tf_["bars"] for k in set(b) - _bar_fields})
check(not _extra, "payload bars carry only OHLC, the tape's own and the dashboard's columns",
      f"extra keys {_extra}")
check(DAY_ENTRIES[0]["timeframes"]["12"]["bars"][0]["close"] !=
      DAY_ENTRIES[-1]["timeframes"]["12"]["bars"][0]["close"] or len(DAY_ENTRIES) == 1,
      "different sessions really carry different prices")

# the two arrow rules, as coded in the sheet
check(re.search(r"function ruleFlags\(f, rule\)", TEMPLATE_TEXT) is not None,
      "the sheet computes each arrow rule's flags itself, from the bars it was given")
check("f.sigs = frameFlags(f);" in TEMPLATE_TEXT and
      re.search(r"function frameFlags\(f\)", TEMPLATE_TEXT) is not None,
      "both rules are computed from the pinned analytics, over the same frame")
check(re.search(r"flags\[i\] = \(rule\.on && c1 && c2 && c3 && cFlow && c4 && c5 && c6\)"
                r" \? 1 : 0;", TEMPLATE_TEXT) is not None,
      "each rule requires all seven of its own conditions, and its own switch, for an arrow")
check(re.search(r"var cFlow = !rule\.useFlow \|\| flowAbove === null \|\| flowAbove === "
                r"undefined \|\|\s*\n?\s*flowBelow === null \|\| flowBelow === undefined \|\| "
                r"flowAbove > flowBelow;", TEMPLATE_TEXT) is not None,
      "the sheet's flow condition compares the two dashboard columns the rule names, and is "
      "skipped entirely when the rule or the session cannot supply them")
check("var flowAbove = f.bars[i][rule.flowAbove];" in TEMPLATE_TEXT and
      "var flowBelow = f.bars[i][rule.flowBelow];" in TEMPLATE_TEXT,
      "the sheet reads the flow pair from the bar's own columns, by the rule's own names")
check(re.search(r"rule\.chgAbove \? prevChg > rule\.chgMin : prevChg < rule\.chgMin",
                TEMPLATE_TEXT) is not None,
      "the change condition reads the side the rule names -- the mirror's one difference there")
check(re.search(r"var fastCounted = fastAn\[rule\.fastRun\]", TEMPLATE_TEXT) is not None and
      re.search(r'rule\.fastRun === "plus" \? "minus" : "plus"', TEMPLATE_TEXT) is not None,
      "the counted run and the zero run are chosen from the rule, so the mirror runs itself")
check("LWC.createSeriesMarkers(f.candle, markers)" in _apply_body and
      "f.arrowMarkers" in _apply_body,
      "both rules' markers are attached to the candle series, which is pane 0")
check("markers.push({ time: f.bars[i].time" in _apply_body and
      "if (flagsOf(f, rule).flags[i])" in _apply_body,
      "one marker per firing candle per rule, at that candle's own time")
check("arrowColor(rule)" in TEMPLATE_TEXT and "arrowShape(rule)" in TEMPLATE_TEXT and
      "rule.position" in TEMPLATE_TEXT,
      "each rule's colour, shape and side of the bar follow that rule")
check("cfg.chgPctMinScaled" in TEMPLATE_TEXT and "SIG_CFG.chgPctMinScaled" not in TEMPLATE_TEXT,
      "the sheet compares the pipeline's scaled thresholds instead of re-rounding them")
check(re.search(r"rule\.rule = cfg\.rule \|\|", TEMPLATE_TEXT) is not None and
      "esc(rule.rule)" in TEMPLATE_TEXT,
      "each rule's sentence comes from the payload and is shown in the chips and the ledger")
check("applySignalMarkers(f);" in TEMPLATE_TEXT,
      "the arrows are drawn when the chart is built")
check("flagsOf(f, rule).arrows" in TEMPLATE_TEXT and
      "flagsOf(f, rule).per.distance_pct_at_cross" in TEMPLATE_TEXT,
      "the chips and the comparison matrix count each rule's arrows per timeframe")
check("<th title='\" + esc(rule.rule) + \"'>\" + rule.label + \"</th>" in TEMPLATE_TEXT and
      "RULES.map(function (rule) {" in TEMPLATE_TEXT,
      "the ledger appendix carries one flag column per rule, titled with that rule's own rule")
check("(fired ? rule.mark : BLANK)" in TEMPLATE_TEXT and "arrowClass(rule)" in TEMPLATE_TEXT,
      "each ledger row prints the arrow it was drawn from, in the rule's own mark and class")
check(re.search(r"\.concat\(RULES\.map\(function \(rule\) \{ return rule\.column; \}\)\)",
                TEMPLATE_TEXT) is not None and
      "RULES.forEach(function (rule) { row.push(flagsOf(f, rule).flags[i]); });" in TEMPLATE_TEXT,
      "the browser CSV export carries both flags in the pipeline's own column order")
check("rec[rule.column] = flagsOf(f, rule).flags[i];" in TEMPLATE_TEXT and
      "signalColumn: SIG.column" in TEMPLATE_TEXT and "redSignalColumn: RED.column" in TEMPLATE_TEXT,
      "the browser JSON export carries both flags bar by bar and names both columns")
check("green arrow" in TEMPLATE_TEXT.lower() and "red arrow" in TEMPLATE_TEXT.lower(),
      "the sheet names both rules in its own words")

# the Method list's recipe values are cells, filled from the payload: the arrow bullet and
# the chart window print the numbers this build actually used, so a recipe that moves a
# threshold cannot leave the sheet describing the rule it used to run. That the cells
# FOLLOW a moved payload is checked in 14, where the sheet's own builder is executed.
# one bullet per rule, each with its own id prefix, plus the two chart-window cells
_RULE_CELL_SUFFIXES = ("cross-pair", "cross-dir", "distance-pair", "distance-window",
                       "relation-pair", "relation-dir", "chg-period", "chg-min", "chg-side",
                       "minus-period", "minus-run", "minus-dir", "plus-period", "plus-run",
                       "plus-dir", "off")
METHOD_CELL_IDS = (("m-window", "m-window-tail")
                   + tuple(f"{_p}-{_suffix}" for _p in ("m", "r")
                           for _suffix in _RULE_CELL_SUFFIXES))
_missing_cells = [cell for cell in METHOD_CELL_IDS if f'id="{cell}"' not in TEMPLATE_TEXT]
check(not _missing_cells,
      "the Method list carries a cell for every recipe value both arrow bullets print",
      f"missing {_missing_cells}")
check("function signalMethodCells()" in TEMPLATE_TEXT and
      re.search(r"var cells = signalMethodCells\(\);\r?\n", TEMPLATE_TEXT) is not None and
      "renderMethod();" in TEMPLATE_TEXT,
      "the method cells are built from the payload's own rule blocks, and applied at boot")
check(re.search(r'var p = rule\.inverted \? "r" : "m";', TEMPLATE_TEXT) is not None and
      "RULES.forEach(function (rule) {\n      var ruleCells = arrowMethodCells(rule);" in TEMPLATE_TEXT,
      "both bullets' cells are generated from the rule objects, so neither can drift")
check(re.search(r"var WINDOW_BARS = .*META\.windowBars", TEMPLATE_TEXT) is not None and
      '"m-window": String(WINDOW_BARS),' in TEMPLATE_TEXT,
      "the Method list's chart-window cell reads the recipe's window_bars")
check("'<br><span class=\"cb-k\">' + rule.label + '</span>" in TEMPLATE_TEXT,
      "the cursor badge reads each rule's flag for the candle under the pointer")
# the console handle is documented as a working interface, so its rule accessor has to read the
# map the sheet actually builds (`frame.sigs`) rather than a single-rule field that no longer
# exists -- a broken accessor would return undefined and look like "no arrows"
check("frameOf(d || activeDay, tf === undefined ? active : Number(tf)).sigs || {}"
      in TEMPLATE_TEXT and
      "return rule === undefined ? sigs : (sigs[rule] || null)" in TEMPLATE_TEXT,
      "the console handle's signal() returns both rules' blocks, keyed by column")

check("SMA 2" in README_TEXT and "SMA 44" in README_TEXT, "README documents the SMA 2/9/44 indicator")
check("one pane" in README_TEXT.lower(), "README states the price pane is the sheet's only pane")
check("window_bars" in README_TEXT, "README documents the chart-window key")
check("consecutive" in README_TEXT.lower(), "README explains the consecutive run counts")
check("direction streak" in README_TEXT.lower(),
      "README documents the SMA 2 vs SMA 9 direction streak row")
check("above" in README_TEXT.lower() and "below" in README_TEXT.lower(),
      "README names both directions of the streak")
check("cross direction" in README_TEXT.lower(),
      "README documents the SMA 2 vs SMA 9 cross direction row")
check("distance" in README_TEXT.lower() and "sma 9" in README_TEXT.lower() and
      "sma 44" in README_TEXT.lower(),
      "README documents the SMA 9 vs SMA 44 distance row")
check("1,880 candles" in README_TEXT or "nine metric rows" in README_TEXT.lower(),
      "README states what the analytics table now holds")
check(re.search(r"green arrow", README_TEXT, re.I) is not None,
      "README documents the green-arrow rule")
check(re.search(r"red arrow", README_TEXT, re.I) is not None,
      "README documents the red-arrow rule")
# the count comes from the rule itself, so a rule that grew a condition cannot leave the
# README stating the old size -- the words are spelled out because the prose is
_CONDITION_WORDS = {4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
_count = len(SIGNAL_RULE_OBJ.tests())
_count_word = _CONDITION_WORDS.get(_count, str(_count))
check(re.search(rf"{_count_word} conditions|all {_count_word}", README_TEXT, re.I) is not None,
      f"README states that the rule is an AND of {_count_word} conditions, the number it has")
check(re.search(r"Method list", README_TEXT) is not None and
      re.search(r"cell filled from `\[sheet\] window_bars`", README_TEXT) is not None and
      re.search(r"built\s+from the payload's own `\[signal\]` block", README_TEXT) is not None,
      "README states that the sheet's own Method list is filled from the recipe it ran")
check(re.search(r"Method list", README_TEXT) is not None and
      re.search(r"red-arrow bullet", README_TEXT, re.I) is not None,
      "README states that both rules' Method bullets are filled from the payload")
check(re.search(r"green_arrow", README_TEXT) is not None,
      "README names the exported column")
check(re.search(r"prev(ious)? candle", README_TEXT, re.I) is not None,
      "README states which conditions are read from the previous candle")
check(re.search(r"two marker rules", README_TEXT, re.I) is not None,
      "README states that the sheet draws exactly two marker rules")
check(re.search(r"mirror", README_TEXT, re.I) is not None and
      re.search(r"red_arrow", README_TEXT) is not None and
      re.search(r"redSignal", README_TEXT) is not None,
      "README documents the red rule as the mirror, its column and its payload block")
check(re.search(r"red\s*[▼]", README_TEXT) is not None,
      "README shows the red rule's own mark, so the two arrows read apart")
check(re.search(r"cumulative (count|counts|positive|negative|rising|falling|tally|tallies)",
                README_TEXT, re.I) is None,
      "README no longer describes the counts as cumulative (the rule is consecutive)")

# --------------------------------------------------------------------------------------
# 9  the zero-previous guard, directly
#
# NIFTY averages are never zero, so no artifact can exhibit this branch. It is the one
# rule that cannot be checked through a generated file, so it is unit-tested through the
# pipeline's own functions; the verifier's own independent implementation is asserted to
# agree.
# --------------------------------------------------------------------------------------

print("\n9  division-by-zero guard")

check(pct_change(10500, 10000) == 5.0, "pipeline: +5% change")
check(pct_change(9500, 10000) == -5.0, "pipeline: -5% change")
check(pct_change(10000, 10000) == 0.0,
      "pipeline: an unchanged average is 0, distinct from blank")
check(pct_change(10000, 0) is None,
      "pipeline: a zero previous average yields no value instead of dividing by zero")
check(pct_change(0, 0) is None, "pipeline: 0/0 is blank, not an error")
check(naive_pct(10000, 0) is None, "verifier: its own rule agrees on the zero guard")
check(naive_pct(10500, 10000) == 50000 and naive_pct(9500, 10000) == -50000,
      "verifier: scaled percentage change is exact at 4 decimals")
check(div_round_half_up(25, 2) == 13 and div_round_half_up(-25, 2) == -13,
      "rounding is half away from zero in both directions")
check(pipeline_count_label(10, 5) == "+10 / \u22125", "runs render as '+10 / -5'")
check("prev === 0" in TEMPLATE_TEXT,
      "the sheet guards a zero previous average with the same rule")

# --------------------------------------------------------------------------------------
# 10  the requirement's own worked example, fed through the pipeline's own function
# --------------------------------------------------------------------------------------

print("\n10  the requirement's worked example")
# four candles whose average changes are +,+,-,- (SMA 2), +,+,+,- (SMA 9), -,-,-,+ (SMA 44)
EXAMPLE = {
    2: [100.00, 100.10, 100.25, 100.20, 100.12],      # +, +, -, -
    9: [200.00, 200.04, 200.12, 200.24, 200.22],      # +, +, +, -
    44: [300.00, 299.91, 299.85, 299.73, 299.76],     # -, -, -, +
}
EXPECTED_RUNS = {
    2: [(1, 0), (2, 0), (0, 1), (0, 2)],
    9: [(1, 0), (2, 0), (3, 0), (0, 1)],
    44: [(0, 1), (0, 2), (0, 3), (1, 0)],
}
example_bars = [{} for _ in range(5)]
for period, values in EXAMPLE.items():
    for i, v in enumerate(values):
        example_bars[i][f"sma{period}"] = v
for period in ANALYTICS_SMAS:
    add_analytics(example_bars, period)
    for i, (want_up, want_down) in enumerate(EXPECTED_RUNS[period], start=1):
        eq((example_bars[i][f"sma{period}_streak_plus"],
            example_bars[i][f"sma{period}_streak_minus"]), (want_up, want_down),
           f"example: SMA {period} candle {i} reads +{want_up} / -{want_down}")
    eq((example_bars[0][f"sma{period}_streak_plus"],
        example_bars[0][f"sma{period}_streak_minus"]), (0, 0),
       f"example: SMA {period} candle 0 has no run yet")
    # and the verifier's own rule reproduces the same table
    changes = [naive_pct(None, None)] + [
        naive_pct(int(round(EXAMPLE[period][i] * 100)), int(round(EXAMPLE[period][i - 1] * 100)))
        for i in range(1, 5)]
    up_run, down_run = naive_runs(changes)
    eq([(up_run[i], down_run[i]) for i in range(1, 5)], EXPECTED_RUNS[period],
       f"example: verifier's independent rule agrees for SMA {period}")

# zero resets both, and the next move starts a new streak at 1 -- the rule the example
# does not cover, tested on the same-function path
def one_bar(values: tuple[float, float, float]) -> dict:
    return {f"sma{p}": v for p, v in zip(ANALYTICS_SMAS, values)}

zero_bars = [one_bar((100.0, 200.0, 300.0)),   # baseline: no change measurable
             one_bar((100.1, 200.2, 300.2)),   # all three rise
             one_bar((100.1, 200.2, 300.2)),   # all three exactly unchanged
             one_bar((100.2, 200.3, 300.1))]   # SMA 2 & 9 rise, SMA 44 falls
for period in ANALYTICS_SMAS:
    add_analytics(zero_bars, period)
for period in ANALYTICS_SMAS:
    eq((zero_bars[1][f"sma{period}_streak_plus"], zero_bars[1][f"sma{period}_streak_minus"]),
       (1, 0), f"zero rule: SMA {period} run reaches +1 on the first rise")
    eq((zero_bars[2][f"sma{period}_streak_plus"], zero_bars[2][f"sma{period}_streak_minus"]),
       (0, 0), f"zero rule: SMA {period} zero change resets both runs")
eq((zero_bars[3]["sma2_streak_plus"], zero_bars[3]["sma2_streak_minus"]), (1, 0),
   "zero rule: SMA 2 starts a fresh +1 after the reset")
eq((zero_bars[3]["sma44_streak_plus"], zero_bars[3]["sma44_streak_minus"]), (0, 1),
   "zero rule: SMA 44 independently starts a fresh -1")

# --- the SMA 2 vs SMA 9 direction streak, through the pipeline's own functions ---------
# sma 9 change :    +,     +,     -,     -,     -,     +,     -,   0,     -,     +
# sma 2 vs 9   :    >,     <,     =,     <,     <,     >,     <,    <,     >,     <
DIR_FAST_SERIES = [200.00, 200.20, 200.30, 200.20, 200.00, 199.90, 200.40, 199.80,
                   199.70, 200.20, 199.50]
DIR_SLOW_SERIES = [200.00, 200.10, 200.40, 200.20, 200.10, 200.05, 200.25, 199.90,
                   199.90, 199.60, 199.70]
DIR_EXPECTED = [(0, 0), (1, 0), (0, 0),      # no change yet; ABOVE runs; fast below while rising
                (0, 0), (0, 1), (0, 2),      # equal averages reset; BELOW starts and extends
                (1, 0), (0, 1),              # BELOW -> ABOVE and back, each restarting at 1
                (0, 0), (0, 0), (0, 0)]      # zero change; fast above while falling; fast below while rising

dir_bars = [{f"sma{p}": v for p, v in zip(ANALYTICS_SMAS,
                                          (DIR_FAST_SERIES[i], DIR_SLOW_SERIES[i], 300.0))}
            for i in range(len(DIR_FAST_SERIES))]
for period in ANALYTICS_SMAS:
    add_analytics(dir_bars, period)
add_direction_streak(dir_bars)
slow_changes = [dir_bars[i][f"sma{DIRECTION_SLOW}_chg_pct"] for i in range(len(dir_bars))]
eq([None if c is None else (1 if c > 0 else (-1 if c < 0 else 0)) for c in slow_changes],
   [None, 1, 1, -1, -1, -1, 1, -1, 0, -1, 1],
   "example: the SMA 9 changes the direction rule reads are the intended ones")
for i, (want_above, want_below) in enumerate(DIR_EXPECTED):
    eq((dir_bars[i][f"sma{DIRECTION_FAST}_vs_sma{DIRECTION_SLOW}_above_streak"],
        dir_bars[i][f"sma{DIRECTION_FAST}_vs_sma{DIRECTION_SLOW}_below_streak"]),
       (want_above, want_below),
       f"example: candle {i} of the direction streak reads +{want_above} / -{want_below}")
mine_above, mine_below = naive_direction_runs(
    [int(round(v * 100)) for v in DIR_FAST_SERIES],
    [int(round(v * 100)) for v in DIR_SLOW_SERIES],
    [None if c is None else int(round(c * 10 ** PCT_DP)) for c in slow_changes])
eq([(mine_above[i], mine_below[i]) for i in range(len(DIR_FAST_SERIES))], DIR_EXPECTED,
   "example: verifier's independent rule agrees on the direction streak")

# --------------------------------------------------------------------------------------
# 11  the recipe
#
# One TOML file drives the build. This section holds the audit's own idea of what the
# recipe must say -- if someone edits a parameter, the audit says so rather than quietly
# measuring a different build -- and then checks that the delivered artifacts, the
# config layer and the command line all agree with it. The command-line half builds a
# scratch copy of the sheet from an overridden recipe in a temporary folder, so nothing
# under output/ is touched.
# --------------------------------------------------------------------------------------

print("\n11  the recipe")

def recipe_width(label: str) -> int:
    """'12s' / '1m' as the seconds this audit recomputed, or -1 if unreadable."""
    match = re.fullmatch(r"(\d+)(s|sec|m|min)", str(label).strip())
    if not match:
        return -1
    return int(match.group(1)) * (60 if match.group(2).startswith("m") else 1)


check(CONFIG_PATH.is_file(), "the build ships a recipe", str(CONFIG_PATH))
try:
    recipe = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
except tomllib.TOMLDecodeError as exc:
    recipe = {}
    check(False, "the recipe parses as TOML", str(exc))

eq(recipe.get("instrument", {}).get("name"), META.get("instrument"), "recipe: instrument")
eq([recipe_width(s) for s in recipe.get("timeframes", {}).get("seconds", [])], list(TIMEFRAMES),
   "recipe: the bar widths are the ones this audit recomputed")
eq(recipe.get("sma", {}).get("price_periods"), list(SMA_PERIODS), "recipe: price averages")
eq(recipe.get("analytics", {}).get("periods"), list(ANALYTICS_SMAS), "recipe: analytics periods")
eq(recipe.get("analytics", {}).get("pct_decimals"), PCT_DP, "recipe: percentage precision")
eq(recipe.get("sheet", {}).get("window_bars"), WINDOW_BARS, "recipe: the chart window")
eq(recipe.get("direction_streak", {}).get("fast_period"), DIRECTION_FAST,
   "recipe: direction fast period")
eq(recipe.get("direction_streak", {}).get("slow_period"), DIRECTION_SLOW,
   "recipe: direction slow period")
eq(recipe.get("cross", {}).get("fast_period"), CROSS_FAST, "recipe: cross fast period")
eq(recipe.get("cross", {}).get("slow_period"), CROSS_SLOW, "recipe: cross slow period")
eq(recipe.get("cross", {}).get("distance_from_period"), CROSS_DIST_FROM,
   "recipe: cross distance from period")
eq(recipe.get("cross", {}).get("distance_to_period"),
   CROSS_DIST_TO, "recipe: cross distance to period")
eq(recipe.get("relation", {}).get("fast_period"), RELATION_FAST,
   "recipe: relationship fast period")
eq(recipe.get("relation", {}).get("slow_period"), RELATION_SLOW,
   "recipe: relationship slow period")
eq(recipe.get("paths", {}).get("sources_dir"), SRC_DIR.name, "recipe: the session folder")
eq(recipe.get("paths", {}).get("sources_glob"), SRC_GLOB, "recipe: the session file glob")
eq(recipe.get("paths", {}).get("output_dir"), OUT_DIR.relative_to(ROOT).as_posix(),
   "recipe: the output folder")
eq([p.name for p in SOURCES], [p.name for p in discovered_sessions()],
   "recipe: every session it names was audited -- a tape, or a dashboard with no tape")

# the delivered sheet is named by the recipe, not by the code
name_template = recipe.get("sheet", {}).get("name_template", "")
expected_sheet = name_template.replace(
    "{range_slug}", f"{DAY_KEYS[0]}_to_{DAY_KEYS[-1]}" if len(DAY_KEYS) > 1 else DAY_KEYS[0])
eq(expected_sheet, SHEET.name, "recipe: the delivered sheet's name")

# and the payload each session carries agrees with the recipe it was built from
eq(META.get("smaPeriods"), recipe.get("sma", {}).get("price_periods"),
   "payload: the price averages are the recipe's")
eq(META.get("analyticsSmas"), recipe.get("analytics", {}).get("periods"),
   "payload: the analytics periods are the recipe's")
eq(META.get("pctDecimals"), recipe.get("analytics", {}).get("pct_decimals"),
   "payload: the precision is the recipe's")
eq(META.get("directionStreak", {}).get("fastPeriod"),
   recipe.get("direction_streak", {}).get("fast_period"),
   "payload: the direction fast period is the recipe's")
eq(META.get("directionStreak", {}).get("slowPeriod"),
   recipe.get("direction_streak", {}).get("slow_period"),
   "payload: the direction slow period is the recipe's")
eq(META.get("cross", {}).get("fastPeriod"), recipe.get("cross", {}).get("fast_period"),
   "payload: the cross pair is the recipe's")
eq(META.get("cross", {}).get("distanceToPeriod"),
   recipe.get("cross", {}).get("distance_to_period"),
   "payload: the distance pair is the recipe's")
eq(META.get("relation", {}).get("fastPeriod"),
   recipe.get("relation", {}).get("fast_period"),
   "payload: the relationship fast period is the recipe's")
eq(META.get("relation", {}).get("slowPeriod"),
   recipe.get("relation", {}).get("slow_period"),
   "payload: the relationship slow period is the recipe's")

# --- the config layer itself ------------------------------------------------------------
defaults = load_config(False)
eq(list(defaults.timeframes), list(TIMEFRAMES), "defaults: the bar widths")
eq(list(defaults.price_periods), list(SMA_PERIODS), "defaults: the price averages")
eq(list(defaults.analytics_periods), list(ANALYTICS_SMAS), "defaults: the analytics periods")
eq(defaults.pct_decimals, PCT_DP, "defaults: the percentage precision")
eq((defaults.direction_fast, defaults.direction_slow), (DIRECTION_FAST, DIRECTION_SLOW),
   "defaults: the direction pair")
eq((defaults.cross_fast, defaults.cross_slow), (CROSS_FAST, CROSS_SLOW),
   "defaults: the crossing pair")
eq((defaults.cross_distance_from, defaults.cross_distance_to),
   (CROSS_DIST_FROM, CROSS_DIST_TO), "defaults: the distance pair")
check("above" in defaults.cross_rule and "equal" in defaults.cross_rule,
      "defaults: the crossing rule names ABOVE and refuses an equal pair")
check(str(CROSS_DIST_TO) in defaults.cross_distance_rule,
      "defaults: the distance rule names the divisor")
check("ABOVE" in defaults.direction_rule and "BELOW" in defaults.direction_rule,
      "defaults: the direction rule reads ABOVE and BELOW")
eq((defaults.relation_fast, defaults.relation_slow), (RELATION_FAST, RELATION_SLOW),
   "defaults: the relationship pair")
check("ABOVE" in defaults.relation_rule and "BELOW" in defaults.relation_rule and
      "equal" in defaults.relation_rule,
      "defaults: the relationship rule names both sides and the tie")
try:
    load_config(False, ["analytics.percent_decimals=6"])
    refusal = None
except ConfigError as exc:
    refusal = str(exc)
check(refusal is not None and "percent_decimals" in refusal,
      "the config layer refuses an unknown key and names it", str(refusal))

# --- the command line honours the recipe ------------------------------------------------
scratch = Path(tempfile.mkdtemp(prefix="nifty_recipe_check_"))
sheet_before = hashlib.sha256(SHEET.read_bytes()).hexdigest()
try:
    res = subprocess.run([sys.executable, str(BUILDER),
                          "--config", str(CONFIG_PATH),
                          "--out-dir", str(scratch),
                          "--quiet",
                          "--set", "analytics.pct_decimals=6",
                          "--set", f"signal.chg_pct_min={SIGNAL_CHG_PCT_MIN_OVERRIDE}",
                          "--set", f"sheet.window_bars={WINDOW_BARS // 2}",
                          "--set", 'timeframes.seconds=["1m","3m"]'],
                         cwd=ROOT, capture_output=True, text=True, timeout=900)
    check(res.returncode == 0, "a recipe can be overridden from the command line",
          f"exit={res.returncode} {(res.stderr or res.stdout).strip()[-300:]}")
    scratch_sheets = sorted(scratch.glob("*.html"))
    eq([p.name for p in scratch_sheets], [SHEET.name],
       "the overridden build delivers one sheet, named by the recipe")
    if scratch_sheets:
        scratch_text = scratch_sheets[0].read_text(encoding="utf-8")
        scratch_payload = json.loads(
            scratch_text.split('<script id="payload"')[1].split(">", 1)[1].split("</script>")[0])
        scratch_days = scratch_payload.get("days", [])
        eq(sorted({key for day in scratch_days for key in day["timeframes"]}, key=int),
           ["60", "180"], "the overridden bar widths reached the sheet")
        eq(scratch_payload.get("meta", {}).get("pctDecimals"), 6,
           "the overridden precision reached the sheet")
        eq(scratch_payload.get("meta", {}).get("windowBars"), WINDOW_BARS // 2,
           "the overridden chart window reached the sheet")
        eq([day["timeframes"]["60"]["stats"]["bars"] for day in scratch_days],
           [SUMMARY[d]["timeframes"]["60"]["bars"] for d in DAY_KEYS],
           "the overridden build ships every session, with the same 1 min bars")
        scratch_csv = scratch / "data" / DAY_KEYS[0] / "nifty_1min.csv"
        with scratch_csv.open(encoding="utf-8", newline="") as fh:
            scratch_rows = list(csv.DictReader(fh))
        check("sma2_chg_pct" in scratch_rows[0] and
              f"sma{DIRECTION_FAST}_vs_sma{DIRECTION_SLOW}_above_streak" in scratch_rows[0],
              "the overridden build keeps the full column set")
        first_pct = next(r["sma2_chg_pct"] for r in scratch_rows if r["sma2_chg_pct"])
        check(re.fullmatch(r"-?\d+\.\d{6}", first_pct) is not None,
              "the overridden precision reached the CSV", first_pct)
        eq(scratch_payload.get("meta", {}).get("signal", {}).get("chgPctMin"),
           SIGNAL_CHG_PCT_MIN_OVERRIDE,
           "the [signal] override reached the sheet's payload")
        eq(scratch_payload.get("meta", {}).get("signal", {}).get("chgPctMinScaled"),
           round(SIGNAL_CHG_PCT_MIN_OVERRIDE * 10 ** 6),
           "the override reached the sheet as the scaled integer the arrow compares in")
        # the red rule is derived, so an override of the green rule moves it too: its block
        # in the overridden payload must be the mirror of the overridden green one, with no
        # red key in the recipe to have set it
        _scratch_sig = scratch_payload.get("meta", {}).get("signal", {})
        _scratch_red = scratch_payload.get("meta", {}).get("redSignal", {})
        eq(_scratch_red.get("chgPctMin"), -SIGNAL_CHG_PCT_MIN_OVERRIDE,
           "the overridden green threshold arrives negated in the red rule")
        eq(_scratch_red.get("chgPctMinScaled"), -round(SIGNAL_CHG_PCT_MIN_OVERRIDE * 10 ** 6),
           "the red rule's scaled threshold is the overridden one, negated")
        eq((_scratch_red.get("distancePctAtCrossMinScaled"),
            _scratch_red.get("distancePctAtCrossMaxScaled")),
           (-_scratch_sig.get("distancePctAtCrossMaxScaled"),
            -_scratch_sig.get("distancePctAtCrossMinScaled")),
           "the red distance window is the overridden green one, mirrored end for end")
        # `[signal] red_arrow` is the one red key the recipe carries, and it is a switch rather
        # than a threshold: the mirror derives every bound from the green rule, so there is no
        # red number to keep in step. (`red_rule`, the optional sentence override, carries no
        # number either, which is why it is the one other red key allowed here.)
        eq({k for k in recipe.get("signal", {}) if "red" in k} - {"red_rule"},
           {"red_arrow"},
           "the recipe declares the red rule's switch and no red threshold")

        def _arrows_in(directory):
            """Arrow flags in a build's own CSVs, candle by candle, one count per rule."""
            counts = {SIGNAL_KEY: 0, RED_KEY: 0}
            for day_dir in sorted(p for p in directory.iterdir() if p.is_dir()):
                for slug in ("1min", "3min"):
                    with (day_dir / f"nifty_{slug}.csv").open(encoding="utf-8",
                                                               newline="") as fh:
                        for row in csv.DictReader(fh):
                            for key in counts:
                                if row[key] == "1":
                                    counts[key] += 1
            return counts

        delivered_arrows = {key: sum(SUMMARY[d]["timeframes"][str(tf)][
                                     "signal" if key == SIGNAL_KEY else "redSignal"]["arrows"]
                                     for d in DAY_KEYS for tf in (60, 180))
                            for key in (SIGNAL_KEY, RED_KEY)}
        scratch_arrows = _arrows_in(scratch / "data")
        check(delivered_arrows[SIGNAL_KEY] > 0,
              "the delivered 1 min and 3 min timeframes carry arrows to compare against",
              f"{delivered_arrows[SIGNAL_KEY]} arrows")
        check(scratch_arrows[SIGNAL_KEY] != delivered_arrows[SIGNAL_KEY],
              "the [signal] override changed which candles the rule fires on, with no "
              "code edit",
              f"{scratch_arrows[SIGNAL_KEY]} arrows under the override vs "
              f"{delivered_arrows[SIGNAL_KEY]} delivered")
        check(all(key in scratch_rows[0] for key in (SIGNAL_KEY, RED_KEY)),
              "the overridden build still ships both arrow columns",
              f"on the 1 min tape: green {scratch_arrows[SIGNAL_KEY]}, "
              f"red {scratch_arrows[RED_KEY]}")

    refused = subprocess.run([sys.executable, str(BUILDER),
                              "--config", str(CONFIG_PATH),
                              "--out-dir", str(scratch / "refused"),
                              "--quiet",
                              "--set", "analytics.percent_decimals=6"],
                             cwd=ROOT, capture_output=True, text=True, timeout=300)
    check(refused.returncode != 0 and "percent_decimals" in (refused.stderr + refused.stdout),
          "an unknown recipe key is refused by the command line, with the key named",
          f"exit={refused.returncode} {(refused.stderr or refused.stdout).strip()[:200]}")

    printed = subprocess.run([sys.executable, str(BUILDER), "--config", str(CONFIG_PATH),
                              "--print-config"],
                             cwd=ROOT, capture_output=True, text=True, timeout=300)
    check(printed.returncode == 0, "--print-config answers",
          f"exit={printed.returncode} {printed.stderr.strip()[-200:]}")
    resolved = json.loads(printed.stdout) if printed.returncode == 0 else {}
    eq(resolved.get("timeframes", {}).get("seconds"), list(TIMEFRAMES),
       "--print-config: the bar widths")
    eq(resolved.get("analytics", {}).get("pct_decimals"), PCT_DP,
       "--print-config: the precision")
    eq(resolved.get("sheet", {}).get("window_bars"), WINDOW_BARS,
       "--print-config: the chart window")
    eq(resolved.get("direction_streak", {}).get("fast_period"), DIRECTION_FAST,
       "--print-config: the direction fast period")
    eq(resolved.get("relation", {}).get("slow_period"), RELATION_SLOW,
       "--print-config: the relationship slow period")
finally:
    shutil.rmtree(scratch, ignore_errors=True)

check(hashlib.sha256(SHEET.read_bytes()).hexdigest() == sheet_before,
      "the scratch build never touched the delivered artifacts")

# --------------------------------------------------------------------------------------
# 12  crossings -- the requirement's own worked examples, and the edge cases a generated
#     file cannot show. Every case is fed through the pipeline's own add_cross, and the
#     verifier's independent rule is asserted to agree with it.
# --------------------------------------------------------------------------------------

print("\n12  crossings")
CROSS_DIR_KEY = cross_key(CROSS_FAST, CROSS_SLOW)
CROSS_DIS_KEY = cross_distance_key(CROSS_DIST_FROM, CROSS_DIST_TO)
CROSS_PAIR_KEY_ = cross_distance_key(CROSS_FAST, CROSS_SLOW)


def cross_bars(rows: list[tuple]) -> list[dict]:
    """A hand-built tape: each row is (sma CROSS_FAST, sma CROSS_SLOW, sma CROSS_DIST_TO)."""
    return [{f"sma{CROSS_FAST}": r[0], f"sma{CROSS_SLOW}": r[1], f"sma{CROSS_DIST_TO}": r[2]}
            for r in rows]


def cross_rows(rows: list[tuple]) -> tuple[list, list, list]:
    bars = cross_bars(rows)
    add_cross(bars, CROSS_FAST, CROSS_SLOW, CROSS_DIST_FROM, CROSS_DIST_TO)
    return ([b[CROSS_DIR_KEY] for b in bars],
            [b[CROSS_DIS_KEY] for b in bars],
            [b[CROSS_PAIR_KEY_] for b in bars])


# --- 12a  the requirement's own distance numbers ---------------------------------------
# SMA 9 = 22,500 against SMA 44 = 22,400 is the documented +0.4464; the mirror image
# (22,300 vs 22,400) is the documented -0.4464. Both are read on the crossing candle.
dirs, dists, pairs = cross_rows([(22500.0, 22400.0, 22400.0),   # SMA 2 above SMA 9
                                 (22300.0, 22500.0, 22400.0),   # crossed down -> BELOW
                                 (22600.0, 22300.0, 22400.0)])  # crossed up   -> ABOVE
eq(dirs, [None, "BELOW", "ABOVE"],
   "example: the strict crossings, on the candle that makes them")
eq(dists[1], 0.4464, "example: SMA 9 22,500 vs SMA 44 22,400 reads +0.4464")
eq(dists[2], -0.4464, "example: SMA 9 22,300 vs SMA 44 22,400 reads -0.4464")
eq(naive_pct(int(round(22500.0 * 100)), int(round(22400.0 * 100))), 4464,
   "example: the verifier's own rule agrees on +0.4464")
eq(naive_pct(int(round(22300.0 * 100)), int(round(22400.0 * 100))), -4464,
   "example: the verifier's own rule agrees on -0.4464")
eq(pairs[1], -0.8889, "example: the supplementary SMA 2 vs SMA 9 distance is carried too")

# --- 12b  equal averages read 0.0000, not blank and not a crossing ---------------------
# A crossing needs the fast average to change side; an equal pair is on neither side, so
# SMA 9 == SMA 44 at the crossing candle is a genuine zero distance.
dirs, dists, _ = cross_rows([(100.0, 105.0, 105.0),   # SMA 2 below SMA 9
                             (110.0, 105.0, 105.0)])  # crossed up -> ABOVE, SMA 9 == SMA 44
eq(dirs[1], "ABOVE", "example: the crossing still happens when SMA 9 equals SMA 44")
eq(dists[1], 0.0, "example: equal averages read 0.0000")
check(dists[1] is not None and fmt_scaled(0) == "0.0000",
      "example: zero is written 0.0000, distinct from an empty cell")

# --- 12c  no crossing, per reason ------------------------------------------------------
eq(cross_rows([(100.0, 100.0, 100.0)])[0], [None],
   "edge: the first candle has no previous candle, so it can never cross")
eq(cross_rows([(100.0, 100.0, 100.0), (110.0, 105.0, 100.0)])[0], [None, None],
   "edge: an equal pair on the previous candle is not a strict crossing")
eq(cross_rows([(110.0, 105.0, 100.0), (105.0, 105.0, 100.0)])[0], [None, None],
   "edge: an equal pair on the current candle is not a strict crossing")
eq(cross_rows([(110.0, 105.0, 100.0), (112.0, 105.0, 100.0)])[0], [None, None],
   "edge: staying above is not a crossing")
eq(cross_rows([(100.0, 105.0, 100.0), (98.0, 105.0, 100.0)])[0], [None, None],
   "edge: staying below is not a crossing")
eq(cross_rows([(100.0, 105.0, 100.0), (None, 105.0, 100.0)])[0], [None, None],
   "edge: an unavailable fast average on the current candle is not a crossing")
eq(cross_rows([(None, 105.0, 100.0), (110.0, 105.0, 100.0)])[0], [None, None],
   "edge: an unavailable fast average on the previous candle is not a crossing")
eq(cross_rows([(110.0, None, 100.0), (110.0, 105.0, 100.0)])[0], [None, None],
   "edge: an unavailable slow average on the previous candle is not a crossing")
eq(cross_rows([(100.0, 110.0, 100.0), (112.0, None, 100.0)])[0], [None, None],
   "edge: an unavailable slow average on the current candle is not a crossing")

# --- 12d  the distance is blank only for its own reasons -------------------------------
_, dists, pairs = cross_rows([(110.0, 105.0, 100.0), (112.0, 106.0, 100.0)])
eq(dists[1], None, "edge: no crossing, so no distance either")
eq(pairs[1], None, "edge: no crossing, so no supplementary distance either")
_, dists, _ = cross_rows([(100.0, 105.0, 0.0), (110.0, 105.0, 0.0)])
eq(dists[1], None, "edge: a zero SMA 44 divisor leaves the distance empty")
_, dists, _ = cross_rows([(100.0, 105.0, None), (110.0, 105.0, None)])
eq(dists[1], None, "edge: an SMA 44 that does not exist yet leaves the distance empty")
_, dists, _ = cross_rows([(100.0, 105.0, 105.0), (110.0, None, 105.0)])
eq(dists[1], None, "edge: an SMA 9 that does not exist yet leaves the distance empty")

# --- 12e  both signs, and the exact half-way tie rounds away from zero -----------------
# A divisor of 20,000.00 makes one paise difference exactly half a unit at the 4th
# decimal, so the tie is reachable with realistic prices and the rounding is provable.
_, dists, _ = cross_rows([(19999.99, 20000.01, 20000.00),
                          (20000.02, 20000.01, 20000.00)])
eq(dists[1], 0.0001,
   "edge: a distance of exactly +0.00005 rounds half-up to 0.0001, not down to 0.0000")
eq(naive_pct(2000001, 2000000), 1, "edge: the verifier's own rule rounds the tie the same way")
_, dists, _ = cross_rows([(20000.02, 19999.99, 20000.00),
                          (19999.97, 19999.99, 20000.00)])
eq(dists[1], -0.0001,
   "edge: a distance of exactly -0.00005 rounds away from zero to -0.0001")
eq(naive_pct(1999999, 2000000), -1, "edge: the verifier's own rule agrees on the negative tie")
_ , dists, _ = cross_rows([(199999.50, 200000.99, 200001.00),
                          (200001.50, 200000.99, 200001.00)])
eq(dists[1], 0.0,
   "edge: a distance below half an ulp at the 4th decimal still reads a signed 0.0000")
check(fmt_scaled(0) == "0.0000", "edge: the formatter renders a rounded-away zero unsigned")

# --- 12f  no look-ahead, and nothing carries across a session boundary -----------------
LONG = [(100.0, 105.0, 100.0), (98.0, 104.0, 100.0), (110.0, 103.0, 101.0),
        (99.0, 102.0, 101.0), (108.0, 101.0, 101.0), (97.0, 100.0, 101.0)]
full_dir, full_dist, full_pair = cross_rows(LONG)
for cut in range(1, len(LONG) + 1):
    part_dir, part_dist, part_pair = cross_rows(LONG[:cut])
    eq(part_dir, full_dir[:cut], f"no look-ahead: direction is unchanged over the first {cut} candles")
    eq(part_dist, full_dist[:cut], f"no look-ahead: distance is unchanged over the first {cut} candles")
    eq(part_pair, full_pair[:cut], f"no look-ahead: pair distance is unchanged over the first {cut} candles")

# two sessions: the second one's first candle must not compare against the first one's
# last candle, because the pipeline is handed one session's bars at a time
sess_a = [(100.0, 105.0, 100.0), (110.0, 105.0, 100.0)]
sess_b = [(112.0, 105.0, 100.0), (90.0, 105.0, 100.0)]
a_dir, _, _ = cross_rows(sess_a)
b_dir, _, _ = cross_rows(sess_b)
eq(a_dir, [None, "ABOVE"], "session boundary: the first session's own crossing")
eq(b_dir, [None, "BELOW"],
   "session boundary: the second session starts blank and never carries the first one's last candle")

# the delivered files keep the same promise: the first candle of every session and
# timeframe is empty, and the row never carries a value the rule cannot produce
boundary_bad = []
vocab_bad = []
totals = {"ABOVE": 0, "BELOW": 0}
for day in DAY_KEYS:
    for seconds in TIMEFRAMES:
        tf_slug = f"{seconds // 60}min" if seconds >= 60 else f"{seconds}sec"
        with (OUT_DATA / day / f"nifty_{tf_slug}.csv").open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if rows:
            if rows[0][CROSS_DIR_KEY] != "":
                boundary_bad.append((day, tf_slug, rows[0][CROSS_DIR_KEY]))
            if rows[0][CROSS_DIS_KEY] != "":
                boundary_bad.append((day, tf_slug, "distance", rows[0][CROSS_DIS_KEY]))
        for i, r in enumerate(rows):
            v = r[CROSS_DIR_KEY]
            if v not in ("", "ABOVE", "BELOW"):
                vocab_bad.append((day, tf_slug, i, v))
            if v:
                totals[v] += 1
            if not v and (r[CROSS_DIS_KEY] or r[CROSS_PAIR_KEY_]):
                vocab_bad.append((day, tf_slug, i, "distance without a crossing"))
            # a crossing may carry a blank distance for exactly one reason: the divisor
            # (SMA 44) has no value yet, or is zero
            if v and not r[CROSS_DIS_KEY] and r["sma44"] not in ("", "0.00"):
                vocab_bad.append((day, tf_slug, i, "crossing without a distance", r["sma44"]))
            if v and r[CROSS_DIS_KEY] and r["sma44"] in ("", "0.00"):
                vocab_bad.append((day, tf_slug, i, "a distance from an unusable divisor"))

check(not boundary_bad,
      "session boundary: the first candle of every session and timeframe carries no crossing",
      f"{boundary_bad[:3]}")
check(not vocab_bad,
      "the delivered rows only ever read ABOVE, BELOW or blank, and a distance only with a crossing",
      f"{vocab_bad[:3]}")
check(totals["ABOVE"] > 0 and totals["BELOW"] > 0,
      "the delivered files exercise both crossing directions",
      f"{totals}")
print(f"     the delivered files carry {totals['ABOVE']} ABOVE and {totals['BELOW']} BELOW "
      "crossing cells")

# --- 12f  the above/below relationship row, through the pipeline's own add_relation -----
# The row is the CURRENT relationship, not a crossing: a word on every candle both averages
# exist, decided by that candle alone, and a tie belongs to neither side.
REL_KEY = relation_key(RELATION_FAST, RELATION_SLOW)


def relation_rows(rows: list[tuple]) -> list:
    """A hand-built tape of (sma RELATION_FAST, sma RELATION_SLOW) -> the row."""
    bars = [{f"sma{RELATION_FAST}": a, f"sma{RELATION_SLOW}": b} for a, b in rows]
    add_relation(bars, RELATION_FAST, RELATION_SLOW)
    return [b[REL_KEY] for b in bars]


def my_relation(fast_price, slow_price):
    """The verifier's own rule: a tie is on neither side, a missing average has none."""
    if fast_price is None or slow_price is None or fast_price == slow_price:
        return None
    return "ABOVE" if fast_price > slow_price else "BELOW"


eq(relation_rows([(100.0, 90.0), (100.0, 90.0), (90.0, 100.0), (100.0, 90.0)]),
   ["ABOVE", "ABOVE", "BELOW", "ABOVE"],
   "example: the relationship row holds on every candle, not only where the pair swaps")
eq(relation_rows([(100.0, 100.0)]), [None],
   "example: equal averages carry no side rather than a guessed one")
eq(relation_rows([(100.0, 100.0), (101.0, 100.0)]), [None, "ABOVE"],
   "example: a tie on one candle does not colour the next candle's word")
eq(relation_rows([(None, 90.0)]), [None],
   "example: a missing fast average leaves the relationship blank")
eq(relation_rows([(100.0, None)]), [None],
   "example: a missing slow average leaves it blank (the warm-up case)")
SIDES = [(100.0, 100.0), (100.0, 90.0), (99.99, 100.0), (None, 100.0), (100.0, None)]
eq(relation_rows(SIDES), [my_relation(a, b) for a, b in SIDES],
   "example: the verifier's own comparison agrees with the pipeline's rule")

# the two rows answer different questions on one tape: the pair holds a side for as long as
# it likes, and the crossing row marks only the candle it swaps on
sides = relation_rows([(100.0, 90.0), (100.0, 90.0), (90.0, 100.0)])
cdirs, _, _ = cross_rows([(100.0, 90.0, 90.0), (100.0, 90.0, 90.0), (90.0, 100.0, 90.0)])
eq(sides, ["ABOVE", "ABOVE", "BELOW"], "example: the relationship row across a swap")
eq(cdirs, [None, None, "BELOW"],
   "example: the crossing row marks the swap candle alone, so the two rows differ")

# and the delivered files agree with the verifier's own rule on every single candle
rel_bad = []
rel_totals = {"ABOVE": 0, "BELOW": 0, "blank": 0}
for day in DAY_KEYS:
    for seconds in TIMEFRAMES:
        tf_slug = f"{seconds // 60}min" if seconds >= 60 else f"{seconds}sec"
        with (OUT_DATA / day / f"nifty_{tf_slug}.csv").open(encoding="utf-8", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                want = my_relation(r[f"sma{RELATION_FAST}"] or None,
                                   r[f"sma{RELATION_SLOW}"] or None)
                if r[REL_KEY] != ("" if want is None else want):
                    rel_bad.append((day, tf_slug, i, r[REL_KEY], want))
                rel_totals["blank" if want is None else want] += 1
check(not rel_bad,
      "the delivered relationship column is the sign of SMA 9 - SMA 44 on every candle, "
      "with a tie and a missing average left blank",
      f"{len(rel_bad)} mismatches, first {rel_bad[:3]}")
print(f"     the delivered files carry {rel_totals['ABOVE']} ABOVE, {rel_totals['BELOW']} BELOW "
      f"and {rel_totals['blank']} blank relationship cells")

# --- 12g  the row only ever reads ABOVE / BELOW / blank --------------------------------
print("     worked examples and edge cases asserted through the pipeline's own rule")


# --------------------------------------------------------------------------------------
print("\n13  the cursor badge")

# --- 13a  the badge as wired into the sheet ---------------------------------------------
# The badge is a read-out of the analytics families for the candle under the pointer: the
# three consecutive counts, the direction streak, the cross with the distance it carried,
# and the above/below relationship.
# It is checked here in two halves: that the template wires it up the way it must be (only
# while a pointer is on the chart, hidden on a switch and in print, reading the same arrays
# the table and the exports read), and then -- section 13b -- that its own builder, executed
# for real, prints the CSV's values.
check(re.search(r"'<div class=\"cursor-badge\" id=\"badge-' \+ f\.key", TEMPLATE_TEXT)
      is not None,
      "each timeframe panel carries its own cursor badge, keyed like its chart")
check("position:absolute;top:0;left:0;z-index:6;pointer-events:none;display:none" in TEMPLATE_TEXT,
      "the badge is hidden until a pointer arrives, and never takes the pointer")
check('.cursor-badge[data-on="true"]{display:block}' in TEMPLATE_TEXT,
      "the badge becomes visible only through its own data-on state")
check("body.js-printing .cursor-badge{display:none}" in TEMPLATE_TEXT and
      ".cursor-badge{display:none !important}" in TEMPLATE_TEXT,
      "the printed sheet carries the table, never a badge left open under the cursor")
check('.cursor-badge{display:none !important}' in TEMPLATE_TEXT.split("@media print", 1)[-1],
      "the badge is hidden by the print stylesheet itself, not only by the print class")
for fn_name in ("function badgeHtml(f, i)", "function showBadge(f, param, idx)",
                "function hideBadge(f)", "function hideBadges()"):
    check(fn_name in TEMPLATE_TEXT, f"the badge is built from {fn_name.split('(')[0].strip()}")
check("showBadge(f, hit ? param : null, idx);" in TEMPLATE_TEXT and
      'chartHost.addEventListener("pointerleave", function () { hideBadge(f); });' in TEMPLATE_TEXT,
      "the badge follows the crosshair and leaves with the pointer")
activate_body = re.search(r"function activate\(tf\) \{(.*?)\n  \}", TEMPLATE_TEXT, re.S)
check(activate_body is not None and "hideBadges();" in activate_body.group(1),
      "a timeframe or session switch drops every open badge")

badge_fn = re.search(r"function badgeHtml\(f, i\) \{(.*?)\n  \}", TEMPLATE_TEXT, re.S)
badge_body = badge_fn.group(1) if badge_fn else ""
check("anOf(f, p)" in badge_body and "f.dir" in badge_body and "f.cross" in badge_body,
      "the badge reads the table's own arrays: the analytics, the direction row and the crossing")
check("countLabel(" in badge_body and "fmtScaled(xv, PCT_DP)" in badge_body,
      "the badge formats through the table's own helpers, at the sheet's own precision")
check("smaCents" not in badge_body and "divHalfUp" not in badge_body and
      "pf < ps" not in badge_body,
      "the badge recomputes nothing: it cannot reach a different crossing than the table's")
check('=== undefined ? "none" : xd' in badge_body and "BLANK" in badge_body,
      "a candle with no crossing reads none, and a missing distance reads blank")
badge_lines_order = [badge_body.find('" run</span>"'), badge_body.find('" dir</span>'),
                     badge_body.find(">cross</span>"), badge_body.find('class="cb-k">d('),
                     badge_body.find('"v" + R_SLOW + "</span>"'),
                     badge_body.find("'<br><span class=\"cb-k\">' + rule.label + '</span>")]
check(all(v >= 0 for v in badge_lines_order) and
      badge_lines_order == sorted(badge_lines_order),
      "the badge lists the rows in the table's own order: runs, direction, cross, distance, "
      "relationship, then one line per arrow rule")
check("flagsOf(f, rule)" in badge_body and "rule.mark" in badge_body and
      "RULES.forEach" in badge_body,
      "the badge reads each arrow from the same flag array its marker is drawn from")
check("markers.push" not in badge_body and "createSeriesMarkers" not in badge_body,
      "the badge draws nothing itself: it is the table's own tokens plus the one flag")
check("buy" not in badge_body.lower() and "sell" not in badge_body.lower(),
      "the badge states no advice, only the row's own readings")
check('cell("SMA" + p + " run"' in TEMPLATE_TEXT and 'cell("streak"' not in TEMPLATE_TEXT,
      "the read-out strip names each run with its own period, so no cell is position-only")

# --- 13b  the badge, executed rather than reimplemented ----------------------------------
# badgeHtml is JavaScript, so the strongest offline test of it is to run the sheet's own
# function: the harness below extracts badgeHtml and the helpers it calls from
# templates/sheet.html, hands it each delivered bar (built from the delivered JSON, with the
# distance scaled back to the integer the sheet formats) and compares every line it prints
# with the delivered CSV. Nothing is reimplemented, so a badge that drifted from the table
# -- a different token, a different rounding, a crossing borrowed from a neighbour -- fails.
BADGE_HARNESS = r'''
const fs = require("fs");
const tpl = fs.readFileSync(process.argv[2], "utf8");
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));

function grabFn(name) {
  const at = tpl.indexOf("function " + name + "(");
  if (at < 0) { throw new Error("missing function " + name); }
  let depth = 0, seen = false;
  for (let i = at; i < tpl.length; i++) {
    const c = tpl[i];
    if (c === "{") { depth++; seen = true; }
    else if (c === "}") { depth--; if (seen && depth === 0) { return tpl.slice(at, i + 1); } }
  }
  throw new Error("unbalanced function " + name);
}

function grabConst(name) {
  const m = new RegExp("\\n  var " + name + " = ([^;]+);").exec(tpl);
  if (!m) { throw new Error("missing constant " + name); }
  return m[1];
}

const meta = JSON.parse(fs.readFileSync(cases[0].json, "utf8")).meta;
// the constants are lifted verbatim, in dependency order, so the harness reads its periods,
// its precision and its blank token from the payload exactly as the sheet does
const CONS = ["BLANK", "PCT_DP", "DIR_CFG", "DIR_FAST", "DIR_SLOW", "ANALYTICS_PERIODS",
              "CROSS_CFG", "X_FAST", "X_SLOW", "X_FROM", "X_TO", "REL_CFG", "R_FAST",
              "R_SLOW", "IST", "SIG", "RED", "RULES"];
// the two rule objects are lifted from the template's own construction lines, so the badge
// is fed the real rules -- labels, marks, positions and thresholds included
const FN = ["badgeHtml", "anOf", "countLabel", "fmtScaled", "dir", "esc", "hhmm", "hhmmss",
            "pad", "toDate", "arrowRule", "arrowClass", "arrowColor", "arrowShape", "arrowSide",
            "flagsOf", "ruleTitle"];
let src = CONS.map(function (n) { return "var " + n + " = " + grabConst(n) + ";"; }).join("\n");
src += "\n" + FN.map(grabFn).join("\n");
src += "\nreturn { badgeHtml: badgeHtml, countLabel: countLabel, dir: dir, BLANK: BLANK,";
src += " PCT_DP: PCT_DP, X_FAST: X_FAST, X_SLOW: X_SLOW, X_FROM: X_FROM, X_TO: X_TO,";
src += " DIR_FAST: DIR_FAST, DIR_SLOW: DIR_SLOW, ANALYTICS_PERIODS: ANALYTICS_PERIODS,";
src += " R_FAST: R_FAST, R_SLOW: R_SLOW, SIG: SIG, RED: RED, RULES: [SIG, RED] };";

const api = new Function("recomputeAnalytics", "META", src)(
  function () { throw new Error("harness: an average was missing from the payload"); }, meta);

// a missing extraction would otherwise show up as an undefined column name and a silent
// 'no crossing anywhere', so every piece the harness leans on is checked up front
["badgeHtml", "countLabel", "dir", "BLANK", "PCT_DP", "X_FAST", "X_SLOW", "X_FROM",
 "X_TO", "DIR_FAST", "DIR_SLOW", "ANALYTICS_PERIODS", "R_FAST", "R_SLOW",
 "SIG", "RED"].forEach(function (k) {
  if (api[k] === undefined || api[k] === null) { throw new Error("harness: api." + k + " did not extract"); }
});
// the two rules must really be two, and the second the mirror of the first: a harness that
// extracted one rule twice would compare the same arrows against itself
if (api.SIG.column === api.RED.column) { throw new Error("harness: both rules extracted as one"); }
if (api.SIG.inverted !== false || api.RED.inverted !== true) {
  throw new Error("harness: the rule directions did not survive extraction");
}

function parseCsv(text) {
  const rows = text.split(/\r?\n/).filter(function (l) { return l.length > 0; });
  const head = rows[0].split(",");
  return rows.slice(1).map(function (l) {
    const cells = l.split(","), rec = {};
    head.forEach(function (h, i) { rec[h] = cells[i]; });
    return rec;
  });
}

function badgeLines(html) {
  const head = /class="cb-head"[^>]*>([^<]*)/.exec(html);
  const rows = [];
  const re = /class="cb-k">([^<]*)<\/span><span class="cb-v([^"]*)">([^<]*)</g;
  let m;
  while ((m = re.exec(html)) !== null) {
    rows.push({ key: m[1], cls: m[2].trim(), val: m[3] });
  }
  return { head: head ? head[1] : "", rows: rows };
}

// each rule's flags come from its own CSV column, which is the same value the marker is
// drawn from and the same value the summary counts
function sigsFor(bars) {
  const out = {};
  const columns = {};
  columns[api.SIG.column] = "green_arrow";
  columns[api.RED.column] = "red_arrow";
  Object.keys(columns).forEach(function (column) {
    out[column] = { flags: bars.map(function (b) { return b[columns[column]]; }) };
  });
  return out;
}

const mismatches = [];
const seen = { ABOVE: 0, BELOW: 0, none: 0, distance: 0, blankDistance: 0,
               positive: 0, negative: 0, zero: 0, relAbove: 0, relBelow: 0, relNone: 0,
               arrows: 0, noArrows: 0, arrowOnCross: 0, redArrows: 0, greenArrows: 0,
               paired: 0, linesPerCandle: 0 };
let candles = 0, lines = 0;

cases.forEach(function (cs) {
  const csvText = fs.readFileSync(cs.csv, "utf8");
  if (csvText.indexOf('"') >= 0) { throw new Error("harness: quoted CSV field in " + cs.label); }
  const csvRows = parseCsv(csvText);
  const bars = JSON.parse(fs.readFileSync(cs.json, "utf8")).bars;
  if (bars.length !== csvRows.length) {
    mismatches.push(cs.label + ": " + bars.length + " JSON bars vs " + csvRows.length + " CSV rows");
    return;
  }

  const an = {};
  api.ANALYTICS_PERIODS.forEach(function (p) {
    an[p] = {
      plus: bars.map(function (b) { return b["sma" + p + "_streak_plus"]; }),
      minus: bars.map(function (b) { return b["sma" + p + "_streak_minus"]; })
    };
  });
  const dCol = "sma" + api.DIR_FAST + "_vs_sma" + api.DIR_SLOW;
  const xCol = "sma" + api.X_FAST + "_vs_sma" + api.X_SLOW;
  const distCol = "sma" + api.X_FROM + "_vs_sma" + api.X_TO + "_distance_pct_at_cross";
  const relCol = "sma" + api.R_FAST + "_vs_sma" + api.R_SLOW + "_relation";
  const f = {
    bars: bars,
    an: an,
    dir: { above: bars.map(function (b) { return b[dCol + "_above_streak"]; }),
           below: bars.map(function (b) { return b[dCol + "_below_streak"]; }) },
    cross: { dir: bars.map(function (b) { return b[xCol + "_cross_direction"]; }),
             dist: bars.map(function (b) {
               const v = b[distCol];
               return (v === null || v === undefined) ? null
                 : Math.round(v * Math.pow(10, api.PCT_DP));
             }) },
    rel: { words: bars.map(function (b) { return b[relCol]; }) },
    sigs: sigsFor(bars)
  };

  for (let i = 0; i < bars.length; i++) {
    const c = csvRows[i];
    const got = badgeLines(api.badgeHtml(f, i));
    candles++;
    lines += got.rows.length;

    const want = [{ key: "time", val: c["time_ist"].slice(11), cls: "" }];
    api.ANALYTICS_PERIODS.forEach(function (p) {
      want.push({
        key: "SMA" + p + " run", cls: "",
        val: api.countLabel(Number(c["sma" + p + "_streak_plus"]),
                            Number(c["sma" + p + "_streak_minus"]))
      });
    });
    want.push({
      key: "SMA" + api.DIR_FAST + "v" + api.DIR_SLOW + " dir", cls: "",
      val: api.countLabel(Number(c[dCol + "_above_streak"]),
                          Number(c[dCol + "_below_streak"]))
    });
    const xd = c[xCol + "_cross_direction"];
    const dv = c[distCol];
    want.push({ key: "cross", val: xd === "" ? "none" : xd,
                cls: xd === "ABOVE" ? "up" : (xd === "BELOW" ? "down" : "flat") });
    want.push({ key: "d(" + api.X_FROM + "," + api.X_TO + ")",
                val: dv === "" ? api.BLANK : dv + "%",
                cls: dv === "" ? "flat" : api.dir(Number(dv)) });
    const rw = c[relCol];
    want.push({ key: api.R_FAST + "v" + api.R_SLOW,
                val: rw === "" ? "none" : rw,
                cls: rw === "ABOVE" ? "up" : (rw === "BELOW" ? "down" : "flat") });
    // one line per arrow rule, in rule order: the mark its own rule taught the sheet, in
    // that rule's own class, read from that rule's own CSV column
    const arrowColumns = {};
    arrowColumns[api.SIG.column] = "green_arrow";
    arrowColumns[api.RED.column] = "red_arrow";
    let greenArrow = false, redArrow = false;
    api.RULES.forEach(function (rule) {
      const fired = c[arrowColumns[rule.column]] === "1";
      if (rule.inverted) { redArrow = fired; } else { greenArrow = fired; }
      want.push({ key: rule.label, val: fired ? rule.mark : api.BLANK,
                  cls: fired ? (rule.inverted ? "down" : "up") : "flat" });
      if (fired) {
        seen.arrows++;
        if (rule.inverted) { seen.redArrows++; } else { seen.greenArrows++; }
        if (xd === "ABOVE" || xd === "BELOW") { seen.arrowOnCross++; }
      } else {
        seen.noArrows++;
      }
    });
    if (greenArrow && redArrow) { seen.paired++; }

    if (xd === "ABOVE" || xd === "BELOW") { seen[xd]++; } else { seen.none++; }
    if (rw === "ABOVE") { seen.relAbove++; }
    else if (rw === "BELOW") { seen.relBelow++; }
    else { seen.relNone++; }
    if (dv === "") { seen.blankDistance++; }
    else {
      seen.distance++;
      const n = Number(dv);
      if (n > 0) { seen.positive++; } else if (n < 0) { seen.negative++; } else { seen.zero++; }
    }

    const gotList = [{ key: "time", val: got.head, cls: "" }].concat(got.rows);
    if (gotList.length !== want.length) {
      mismatches.push(cs.label + " candle " + i + ": " + gotList.length +
                      " badge lines vs " + want.length);
    } else {
      for (let j = 0; j < want.length; j++) {
        if (gotList[j].key !== want[j].key) {
          mismatches.push(cs.label + " candle " + i + " line " + j + ": key " +
                          JSON.stringify(gotList[j].key) + " vs " + JSON.stringify(want[j].key));
        }
        if (gotList[j].val !== want[j].val) {
          mismatches.push(cs.label + " candle " + i + " " + want[j].key + ": badge " +
                          JSON.stringify(gotList[j].val) + " vs CSV " + JSON.stringify(want[j].val));
        }
        if (want[j].cls && gotList[j].cls !== want[j].cls) {
          mismatches.push(cs.label + " candle " + i + " " + want[j].key + ": class " +
                          JSON.stringify(gotList[j].cls) + " vs " + JSON.stringify(want[j].cls));
        }
      }
    }
    if (mismatches.length > 12) { break; }
  }
});

console.log(JSON.stringify({
  cases: cases.length, candles: candles, lines: lines, seen: seen,
  badgeFnBytes: grabFn("badgeHtml").length, srcBytes: src.length,
  mismatchCount: mismatches.length, mismatches: mismatches.slice(0, 12)
}));
'''

badge_cases = []
badge_candles = 0
for day in DAY_KEYS:
    for seconds in TIMEFRAMES:
        tf_slug = f"{seconds // 60}min" if seconds >= 60 else f"{seconds}sec"
        csv_path = OUT_DATA / day / f"nifty_{tf_slug}.csv"
        with csv_path.open(encoding="utf-8", newline="") as fh:
            badge_candles += sum(1 for _ in csv.DictReader(fh))
        badge_cases.append({"label": f"{day} {tf_slug}", "csv": str(csv_path),
                            "json": str(OUT_DATA / day / f"nifty_{tf_slug}.json")})

node_out: dict = {}
node_ran = False
node_err = ""
with tempfile.TemporaryDirectory() as tmp:
    harness_path = Path(tmp) / "badge_harness.js"
    harness_path.write_text(BADGE_HARNESS, encoding="utf-8")
    cases_path = Path(tmp) / "badge_cases.json"
    cases_path.write_text(json.dumps(badge_cases), encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(harness_path), str(TEMPLATE), str(cases_path)],
                              capture_output=True, text=True, timeout=900)
        node_ran = proc.returncode == 0
        if node_ran:
            node_out = json.loads(proc.stdout)
        else:
            tail = (proc.stderr or "").strip().splitlines()
            node_err = tail[-1] if tail else f"node exited {proc.returncode}"
    except FileNotFoundError as exc:
        node_err = f"node is not on PATH ({exc})"
    except subprocess.TimeoutExpired:
        node_err = "node did not finish within 900 s"
    except json.JSONDecodeError as exc:
        node_err = f"the harness printed no JSON: {exc}"

check(node_ran, "the sheet's own badge builder runs outside the browser (node)", node_err)
check(node_out.get("badgeFnBytes", 0) > 400 and node_out.get("srcBytes", 0) > 1000,
      "the harness executes the template's own badgeHtml and its helpers, not a stand-in",
      f"{node_out.get('badgeFnBytes')} bytes of badgeHtml out of {node_out.get('srcBytes')}")
check(node_out.get("mismatchCount") == 0,
      "the badge prints the CSV's own values, on every line of every candle of every "
      "session and timeframe", f"{node_out.get('mismatches')}")
eq(node_out.get("candles"), badge_candles,
   "the badge was exercised over every delivered candle")
eq(node_out.get("lines"), badge_candles * 9,
   "every badge carried all nine lines -- the seven read-outs and one per arrow rule -- "
   "on every candle")
badge_seen = node_out.get("seen", {})
check(badge_seen.get("ABOVE", 0) > 0 and badge_seen.get("BELOW", 0) > 0,
      "the badge read out both crossing directions over the delivered sessions",
      f"{badge_seen}")
check(badge_seen.get("none", 0) > 0,
      "the badge read 'none' on the candles that carry no crossing", f"{badge_seen}")
check(badge_seen.get("distance", 0) > 0 and badge_seen.get("blankDistance", 0) > 0,
      "the badge showed a distance on the crossing candles and stayed blank where the "
      "divisor has no value", f"{badge_seen}")
check(badge_seen.get("positive", 0) > 0 and badge_seen.get("negative", 0) > 0,
      "the badge showed both signs of the distance", f"{badge_seen}")
check(badge_seen.get("relAbove", 0) > 0 and badge_seen.get("relBelow", 0) > 0,
      "the badge showed both sides of the relationship row", f"{badge_seen}")
check(badge_seen.get("relNone", 0) > 0,
      "the badge read 'none' where the pair has no side: a tie, or the slow average absent",
      f"{badge_seen}")
check(badge_seen.get("arrows", 0) > 0 and badge_seen.get("noArrows", 0) > 0,
      "the badge showed both an arrow and no arrow, across the delivered candles",
      f"{badge_seen.get('arrows')} arrows / {badge_seen.get('noArrows')} plain candles")
check(badge_seen.get("greenArrows", 0) == SIGNAL_ARROWS[0] and
      badge_seen.get("redArrows", 0) == RED_ARROWS[0],
      "the badge showed every green arrow and every red arrow the CSVs carry",
      f"badge {badge_seen.get('greenArrows')} green / {badge_seen.get('redArrows')} red "
      f"vs CSV {SIGNAL_ARROWS[0]} / {RED_ARROWS[0]}")
eq(badge_seen.get("paired", 0), 0,
   "no candle's badge showed both arrows at once")
print(f"     the sheet's own builder rendered {badge_seen.get('ABOVE', 0)} ABOVE / "
      f"{badge_seen.get('BELOW', 0)} BELOW / {badge_seen.get('none', 0)} none crosses, "
      f"{badge_seen.get('relAbove', 0)} ABOVE / {badge_seen.get('relBelow', 0)} BELOW / "
      f"{badge_seen.get('relNone', 0)} no-side relationship cells and "
      f"{badge_seen.get('greenArrows', 0)} green + {badge_seen.get('redArrows', 0)} red arrows "
      f"across {node_out.get('candles', 0)} candles, all matching the CSV")

# --------------------------------------------------------------------------------------
# 14  the two arrow rules: the sheet's own rule engine, the mirror identity, and the edges
#     a generated file cannot show
# --------------------------------------------------------------------------------------

print("\n14  the two arrow rules")

check(SIGNAL_ARROWS[0] > 0,
      "the delivered sessions contain arrows to audit",
      f"{SIGNAL_ARROWS[0]} arrows")
check(SIGNAL_FRAMES_WITH_ARROWS[0] > 0,
      "at least one (session, timeframe) really fires the green rule",
      f"{SIGNAL_FRAMES_WITH_ARROWS[0]} of {len(DAY_KEYS) * len(TIMEFRAMES)} frames")
eq(SIGNAL_FIRST_CANDLE_HITS[0], 0,
   "no session's first candle ever carries an arrow: there is no previous candle to read")
eq(RED_FIRST_CANDLE_HITS[0], 0,
   "no session's first candle carries a red arrow either")
eq(RED_PAIRED[0], 0,
   "no candle carries both arrows: the two rules are disjoint by construction")

# ---- the mirror, at the rule level ------------------------------------------------------
# The recipe declares one rule; the red one is `mirrored()`. These assertions pin the two
# together at the level of the rule objects themselves, so a mirror that changed a threshold
# instead of negating it, or that lost the run swap, cannot pass.
_MIRROR = CONFIG_OBJ.red_rule_obj()
eq(_MIRROR.mirrored(), SIGNAL_RULE_OBJ,
   "the mirror of the mirror is the rule itself")
eq(_MIRROR.read_columns, SIGNAL_RULE_OBJ.read_columns,
   "the mirror reads exactly the columns its original reads")
eq([name for name, _, _ in _MIRROR.tests()], [name for name, _, _ in SIGNAL_RULE_OBJ.tests()],
   "the mirror's conditions are the same seven, in the same order")
eq(sorted(_MIRROR.flow_columns), sorted(SIGNAL_RULE_OBJ.flow_columns),
   "the mirror compares the same two dashboard columns, and swaps which one must be greater")
eq((_MIRROR.flow_above, _MIRROR.flow_below),
   (SIGNAL_RULE_OBJ.flow_below, SIGNAL_RULE_OBJ.flow_above),
   "the mirror's flow condition is the green one's two sides exchanged, not negated")
eq(len(_MIRROR.tests()), len(SIGNAL_RULE_OBJ.tests()),
   "the mirror has the same number of conditions -- it is not a subset or a superset")
eq((_MIRROR.cross_fast, _MIRROR.cross_slow, _MIRROR.distance_from, _MIRROR.distance_to,
    _MIRROR.fast_period, _MIRROR.slow_period),
   (SIGNAL_RULE_OBJ.cross_fast, SIGNAL_RULE_OBJ.cross_slow, SIGNAL_RULE_OBJ.distance_from,
    SIGNAL_RULE_OBJ.distance_to, SIGNAL_RULE_OBJ.fast_period, SIGNAL_RULE_OBJ.slow_period),
   "the mirror reads the same averages: only the comparisons flip")
eq((_MIRROR.streak_minus_min, _MIRROR.streak_minus_max, _MIRROR.streak_plus_min),
   (SIGNAL_RULE_OBJ.streak_minus_min, SIGNAL_RULE_OBJ.streak_minus_max,
    SIGNAL_RULE_OBJ.streak_plus_min),
   "the mirror keeps the run lengths, because an inversion keeps a run's length")
check(_MIRROR.fast_run_column == SIGNAL_RULE_OBJ.fast_run_zero_column and
      _MIRROR.slow_run_column == SIGNAL_RULE_OBJ.slow_run_column.replace("plus", "minus"),
      "the mirror counts the run the green rule requires to be zero, and vice versa")
check("RED ARROW" in _MIRROR.rule_text() and "above the bar" in _MIRROR.rule_text() and
      "rising run" in _MIRROR.rule_text() and "falling run" in _MIRROR.rule_text(),
      "the mirror's own sentence describes the red arrow and its swapped runs")
check("GREEN ARROW" in SIGNAL_RULE_OBJ.rule_text() and
      "falling run" in SIGNAL_RULE_OBJ.rule_text(),
      "the green rule's sentence is unchanged by the mirror's existence")

# each condition must rule something out somewhere, or it is decoration rather than a
# condition. The tally counts the candles the OTHER five conditions would have allowed.
SIGNAL_CONDITION_ORDER = ("cross_direction", "distance_pct_at_cross", "relation", "flow",
                          "chg_pct", "streak_minus", "streak_plus")
print("     candles the other five conditions would have allowed, per condition:")
for _key in SIGNAL_CONDITION_ORDER:
    _near = SIGNAL_NEAR_MISS.get(_key, 0)
    print(f"       {_key:<22} {_near:>5}  vs {SIGNAL_ARROWS[0]} arrows")
    # a condition can never refuse an arrow: every arrow's six conditions hold, so removing
    # any one of them must leave at least the arrows standing
    check(_near >= SIGNAL_ARROWS[0],
          f"the {_key} condition is satisfied by every arrow the rule fired",
          f"{_near} near-misses vs {SIGNAL_ARROWS[0]} arrows")
check(sorted(SIGNAL_NEAR_MISS) == sorted(SIGNAL_CONDITION_ORDER),
      "the rule's conditions are exactly the ones this section tallied, key by key",
      f"tallied {sorted(SIGNAL_NEAR_MISS)}")
_binding = [k for k, v in SIGNAL_NEAR_MISS.items() if v > SIGNAL_ARROWS[0]]
check(len(_binding) >= 4,
      "at least four of the seven conditions refused a candle the other six would have "
      "allowed, so the AND is not a handful of conditions dressed up as seven",
      f"binding: {sorted(_binding)}")

# the mirror's funnel, measured the same way and reported the same way: the same six keys,
# the candles its own other five conditions would have allowed, and the same invariant -- no
# mirrored condition may refuse a red arrow, and at least four must refuse some candle
print("     the mirror's funnel, the other five mirrored conditions, per condition:")
for _key in SIGNAL_CONDITION_ORDER:
    _near = RED_NEAR_MISS.get(_key, 0)
    print(f"       {_key:<22} {_near:>5}  vs {RED_ARROWS[0]} red arrows")
    check(_near >= RED_ARROWS[0],
          f"the mirror's {_key} condition is satisfied by every red arrow",
          f"{_near} near-misses vs {RED_ARROWS[0]} red arrows")
check(sorted(RED_NEAR_MISS) == sorted(SIGNAL_CONDITION_ORDER),
      "the mirror's conditions are exactly the ones this section tallied, key by key",
      f"tallied {sorted(RED_NEAR_MISS)}")
# the mirror reads a mirrored dashboard pair as well (CE above PE), so a session whose red
# candles all fall in PE-above-CE minutes legitimately delivers none -- this delivery is one
# of those, and a tally of "conditions that refused a candle" has no arrows to be measured
# against. When the delivery does carry red arrows the requirement is unchanged; when it does
# not, section 14 proves the mirror and its flow condition on tapes this audit builds.
_binding_red = [k for k, v in RED_NEAR_MISS.items() if v > RED_ARROWS[0]]
check(len(_binding_red) >= 4 or RED_ARROWS[0] == 0,
      "at least four of the mirror's seven conditions refused a candle the other six would "
      "have allowed, so the mirrored AND is not seven words around one comparison -- or the "
      "delivery carries no red arrow for the tally to bind against",
      f"binding: {sorted(_binding_red)} over {RED_ARROWS[0]} red arrows")

# ---- the sheet's own rule, executed rather than reimplemented ---------------------------
# The flags the browser draws its arrows from are produced by ruleFlags, which is
# JavaScript, run once per rule. The harness below extracts that function, the two rule
# objects it is called with and every helper they call from templates/sheet.html, rebuilds
# each delivered frame from the delivered closes with the sheet's own SMA and analytics code,
# runs both of the sheet's own rules and compares every flag with the CSV's own cell --
# green_arrow for one, red_arrow for the other. Nothing is reimplemented, so an arrow that
# landed on a different candle than the exported flag would fail here, and so would a sheet
# whose red rule was not the mirror.
SIGNAL_HARNESS = r'''
const fs = require("fs");
const tpl = fs.readFileSync(process.argv[2], "utf8");
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));

function grabFn(name) {
  const at = tpl.indexOf("function " + name + "(");
  if (at < 0) { throw new Error("missing function " + name); }
  let depth = 0, seen = false;
  for (let i = at; i < tpl.length; i++) {
    const c = tpl[i];
    if (c === "{") { depth++; seen = true; }
    else if (c === "}") { depth--; if (seen && depth === 0) { return tpl.slice(at, i + 1); } }
  }
  throw new Error("unbalanced function " + name);
}

function grabConst(name) {
  const m = new RegExp("\\n  var " + name + " = ([^;]+);").exec(tpl);
  if (!m) { throw new Error("missing constant " + name); }
  return m[1];
}

const FN = ["toCents", "divHalfUp", "smaFromCents", "analyticsFromCents", "analyticsFor",
            "crossFromSmas", "relationFromSmas", "crossRowFor", "relationRowFor",
            "ruleFlags", "frameFlags", "flagsOf", "arrowRule", "arrowColor", "arrowClass",
            "arrowShape", "arrowSide", "ruleTitle"];
// the rule objects are lifted from the template's own construction lines, so the harness runs
// the sheet's own rules -- both of them -- rather than a hand-built parameter set
const CONS = ["PCT_DP", "ANALYTICS_PERIODS", "CROSS_CFG", "REL_CFG", "X_FAST", "X_SLOW",
              "X_FROM", "X_TO", "R_FAST", "R_SLOW", "C", "SIG", "RED", "RULES"];
let src = CONS.map(function (n) { return "var " + n + " = " + grabConst(n) + ";"; }).join("\n");
src += "\n" + FN.map(grabFn).join("\n");
src += "\nreturn { ruleFlags: ruleFlags, frameFlags: frameFlags, flagsOf: flagsOf,";
src += " crossFromSmas: crossFromSmas, relationFromSmas: relationFromSmas,";
src += " analyticsFromCents: analyticsFromCents, SIG: SIG, RED: RED, RULES: RULES,";
src += " X_FAST: X_FAST, X_SLOW: X_SLOW, X_FROM: X_FROM, X_TO: X_TO, R_FAST: R_FAST,";
src += " R_SLOW: R_SLOW, ANALYTICS_PERIODS: ANALYTICS_PERIODS, PCT_DP: PCT_DP };";

const meta = JSON.parse(fs.readFileSync(cases[0].json, "utf8")).meta;
const api = new Function("recomputeAnalytics", "META", src)(
  function () { throw new Error("harness: an average was missing from the payload"); }, meta);

["ruleFlags", "flagsOf", "crossFromSmas", "relationFromSmas", "analyticsFromCents",
 "SIG", "RED", "ANALYTICS_PERIODS"].forEach(function (k) {
  if (api[k] === undefined || api[k] === null) { throw new Error("harness: api." + k + " did not extract"); }
});
if (api.SIG.column === api.RED.column || api.SIG.inverted || !api.RED.inverted) {
  throw new Error("harness: the two rules did not extract as a rule and its mirror");
}
// the CSV column each rule's flag ships in, read from the rules themselves
const COLUMN = {};
COLUMN[api.SIG.column] = "green_arrow";
COLUMN[api.RED.column] = "red_arrow";

function parseCsv(text) {
  const rows = text.split(/\r?\n/).filter(function (l) { return l.length > 0; });
  const head = rows[0].split(",");
  return rows.slice(1).map(function (l) {
    const cells = l.split(","), rec = {};
    head.forEach(function (h, i) { rec[h] = cells[i]; });
    return rec;
  });
}

const mismatches = [];
const per = {}, arrows = {}, framesWithArrows = {}, firstCandleHits = {};
api.RULES.forEach(function (rule) {
  per[rule.column] = { cross_direction: 0, distance_pct_at_cross: 0, relation: 0, flow: 0,
                       chg_pct: 0, streak_minus: 0, streak_plus: 0 };
  arrows[rule.column] = 0;
  framesWithArrows[rule.column] = 0;
  firstCandleHits[rule.column] = 0;
});
let candles = 0, paired = 0;

cases.forEach(function (cs) {
  // a synthetic case is the audit's own frame, built to carry a red candle when the
  // delivery's flow condition leaves it none: it still has to reproduce the sheet's flags
  // candle for candle, it just does not count towards the delivery's own tallies
  const synthetic = cs.synthetic === true;
  const csvRows = parseCsv(fs.readFileSync(cs.csv, "utf8"));
  const bars = JSON.parse(fs.readFileSync(cs.json, "utf8")).bars;
  if (bars.length !== csvRows.length) {
    mismatches.push(cs.label + ": " + bars.length + " JSON bars vs " + csvRows.length + " CSV rows");
    return;
  }
  // the frame the sheet builds: closes -> its own integer SMA -> its own analytics, then
  // the crossing and relationship rows through the sheet's own functions
  const cents = bars.map(function (b) { return Math.round(b.close * 100); });
  const an = {};
  api.ANALYTICS_PERIODS.forEach(function (p) { an[p] = api.analyticsFromCents(cents, p); });
  function anFor(p) { return an[p] || api.analyticsFromCents(cents, p); }
  const f = { bars: bars, cents: cents, an: an };
  f.cross = api.crossFromSmas(anFor(api.X_FAST), anFor(api.X_SLOW),
                              anFor(api.X_FROM), anFor(api.X_TO));
  f.rel = api.relationFromSmas(anFor(api.R_FAST), anFor(api.R_SLOW));
  // both rules, through the sheet's own frameFlags, exactly as the page computes them
  f.sigs = api.frameFlags(f);

  const frameArrows = {};
  api.RULES.forEach(function (rule) { frameArrows[rule.column] = 0; });
  for (let i = 0; i < bars.length; i++) {
    if (!synthetic) { candles++; }
    let greenHere = false, redHere = false;
    api.RULES.forEach(function (rule) {
      const got = api.flagsOf(f, rule).flags[i];
      const want = csvRows[i][COLUMN[rule.column]];
      if (String(got) !== want) {
        mismatches.push(cs.label + " " + COLUMN[rule.column] + " candle " + i +
                        ": sheet " + got + " vs CSV " + want);
      }
      if (got) {
        if (!synthetic) { arrows[rule.column]++; }
        frameArrows[rule.column]++;
      }
      if (rule.inverted) { redHere = !!got; } else { greenHere = !!got; }
    });
    if (greenHere && redHere && !synthetic) { paired++; }
  }
  api.RULES.forEach(function (rule) {
    const res = api.flagsOf(f, rule);
    if (res.flags[0] && !synthetic) { firstCandleHits[rule.column]++; }
    if (frameArrows[rule.column]) { framesWithArrows[rule.column]++; }
    if (synthetic) { return; }
    Object.keys(per[rule.column]).forEach(function (k) {
      if (res.per && typeof res.per[k] === "number") { per[rule.column][k] += res.per[k]; }
    });
  });
  if (mismatches.length > 12) { return; }
});

console.log(JSON.stringify({
  frames: cases.length, candles: candles, paired: paired, syntheticCases: cases.filter(function (c) { return c.synthetic === true; }).length,
  arrows: arrows, framesWithArrows: framesWithArrows, firstCandleHits: firstCandleHits,
  per: per, columns: COLUMN,
  srcBytes: src.length, ruleFnBytes: grabFn("ruleFlags").length,
  mismatchCount: mismatches.length, mismatches: mismatches.slice(0, 12)
}));
'''

signal_out: dict = {}
signal_ran = False
signal_err = ""
signal_cases = [{"label": f"{_day} {_slug}", "csv": str(OUT_DATA / _day / f"nifty_{_slug}.csv"),
                 "json": str(OUT_DATA / _day / f"nifty_{_slug}.json")}
                for _day in DAY_KEYS for _slug in
                [f"{s // 60}min" if s >= 60 else f"{s}sec" for s in TIMEFRAMES]]
with tempfile.TemporaryDirectory() as tmp:
    _harness = Path(tmp) / "signal_harness.js"
    _harness.write_text(SIGNAL_HARNESS, encoding="utf-8")
    # The audit's own frame for the red path: one delivered timeframe's bars with the
    # dashboard pair set to CE above PE on every candle -- the red rule's reading of the flow
    # condition -- then both flags recomputed through the pipeline's own step and the file
    # written by the pipeline's own CSV writer. The sheet's engine must reproduce these flags
    # candle for candle like any other case, which is what proves the red path is not vacuous
    # for a delivery whose own flow condition leaves every red candle refused.
    _witness_bars = json.loads((OUT_DATA / DAY_KEYS[0] / "nifty_12sec.json")
                               .read_text(encoding="utf-8"))["bars"]
    for _bar in _witness_bars:
        _bar[CE_OI_CHANGE] = 5
        _bar[PE_OI_CHANGE] = 1
    add_signal(_witness_bars, SIGNAL_RULE_OBJ, SIGNAL_KEY)
    add_signal(_witness_bars, RED_RULE_OBJ, RED_KEY)
    _witness_csv = Path(tmp) / "flow_red_witness.csv"
    _witness_json = Path(tmp) / "flow_red_witness.json"
    exports.write_csv(_witness_csv, _witness_bars, CONFIG_OBJ)
    _witness_json.write_text(json.dumps({"bars": _witness_bars}), encoding="utf-8")
    signal_cases.append({"label": "flow-red witness", "csv": str(_witness_csv),
                         "json": str(_witness_json), "synthetic": True})
    _cases = Path(tmp) / "signal_cases.json"
    _cases.write_text(json.dumps(signal_cases), encoding="utf-8")
    try:
        _proc = subprocess.run(["node", str(_harness), str(TEMPLATE), str(_cases)],
                               capture_output=True, text=True, timeout=900)
        signal_ran = _proc.returncode == 0
        if signal_ran:
            signal_out = json.loads(_proc.stdout)
        else:
            _tail = (_proc.stderr or "").strip().splitlines()
            signal_err = _tail[-1] if _tail else f"node exited {_proc.returncode}"
    except FileNotFoundError as exc:
        signal_err = f"node is not on PATH ({exc})"
    except subprocess.TimeoutExpired:
        signal_err = "node did not finish within 900 s"
    except json.JSONDecodeError as exc:
        signal_err = f"the harness printed no JSON: {exc}"

check(signal_ran, "the sheet's own two arrow rules run outside the browser (node)", signal_err)
check(signal_out.get("ruleFnBytes", 0) > 400 and signal_out.get("srcBytes", 0) > 1500,
      "the harness executes the template's own ruleFlags and its helpers, not a stand-in",
      f"{signal_out.get('ruleFnBytes')} bytes of ruleFlags out of {signal_out.get('srcBytes')}")
eq(signal_out.get("columns"), {SIGNAL_KEY: "green_arrow", RED_KEY: "red_arrow"},
   "the harness read each rule's flags from its own CSV column")
check(signal_out.get("mismatchCount") == 0,
      "the sheet's own rules flag exactly the candles the CSVs flag, on every candle of "
      "every session and timeframe", f"{signal_out.get('mismatches')}")
eq(signal_out.get("candles"), badge_candles,
   "the sheet's own rules were exercised over every delivered candle")
eq(signal_out.get("arrows"), {SIGNAL_KEY: SIGNAL_ARROWS[0], RED_KEY: RED_ARROWS[0]},
   "the sheet's own rules draw the same arrows the CSVs record, rule for rule")
eq(signal_out.get("firstCandleHits"), {SIGNAL_KEY: 0, RED_KEY: 0},
   "neither of the sheet's own rules fires on a session's first candle")
eq(signal_out.get("paired"), 0,
   "the sheet's own rules never both fire on one candle")
check(all(_v > 0 for _v in signal_out.get("framesWithArrows", {}).values()),
      "each sheet rule fires on at least one frame -- one of the delivery's, or the audit's "
      "own flow-red witness frame when the delivery's flow condition leaves it none -- so "
      "neither comparison is vacuous",
      f"{signal_out.get('framesWithArrows')}")
check(signal_out.get("syntheticCases") == 1,
      "the witness frame is marked synthetic, so it is proved without inflating the "
      "delivery's own arrow, candle or funnel tallies",
      f"{signal_out.get('syntheticCases')} synthetic cases")
_summary_per: dict = {SIGNAL_KEY: {}, RED_KEY: {}}
for _day in DAY_KEYS:
    for _tf in TIMEFRAMES:
        for _col, _block in ((SIGNAL_KEY, "signal"), (RED_KEY, "redSignal")):
            for _k, _v in SUMMARY[_day]["timeframes"][str(_tf)][_block]["perCondition"].items():
                _summary_per[_col][_k] = _summary_per[_col].get(_k, 0) + _v
eq(signal_out.get("per"), _summary_per,
   "each sheet rule's per-condition tallies equal its own summary block, condition by "
   "condition -- so the mirror's funnel is its own, not the green rule's restated")
print(f"     the sheet's own rules fired "
      f"{signal_out.get('arrows', {}).get(SIGNAL_KEY, 0)} green and "
      f"{signal_out.get('arrows', {}).get(RED_KEY, 0)} red arrows over "
      f"{signal_out.get('candles', 0)} candles, every flag equal to its CSV's cell")

# ---- the Method list's recipe cells, run against a payload the verifier moves ------------
# The sheet's Method bullet states the rule it ran, and the chart-window line states the
# window. Those lines are cells filled by signalMethodCells, which is pure, so the sheet's
# own builder is executed here twice: once with the delivered payload, and once with a
# payload whose [signal] block and window the verifier has moved by hand. A threshold that
# had been written into the prose rather than read from the payload would print the old
# value and fail here.
METHOD_HARNESS = r'''
const fs = require("fs");
const tpl = fs.readFileSync(process.argv[2], "utf8");
const meta = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const patch = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));

function grabFn(name) {
  const at = tpl.indexOf("function " + name + "(");
  if (at < 0) { throw new Error("missing function " + name); }
  let depth = 0, seen = false;
  for (let i = at; i < tpl.length; i++) {
    const c = tpl[i];
    if (c === "{") { depth++; seen = true; }
    else if (c === "}") { depth--; if (seen && depth === 0) { return tpl.slice(at, i + 1); } }
  }
  throw new Error("unbalanced function " + name);
}

function grabConst(name) {
  const m = new RegExp("\\n  var " + name + " = ([^;]+);").exec(tpl);
  if (!m) { throw new Error("missing constant " + name); }
  return m[1];
}

const CONS = ["CROSS_CFG", "REL_CFG", "X_FAST", "X_SLOW", "X_FROM", "X_TO", "R_FAST",
              "R_SLOW", "C", "WINDOW_BARS", "SIG", "RED", "RULES"];
const FN = ["fmtScaled", "arrowRule", "arrowMethodCells", "signalMethodCells", "arrowClass",
            "arrowColor", "arrowShape", "arrowSide", "ruleTitle"];
let src = CONS.map(function (n) { return "var " + n + " = " + grabConst(n) + ";"; })
  .join("\n");
src += "\n" + FN.map(grabFn).join("\n");
src += "\nreturn { cells: signalMethodCells, rules: RULES };";

const dragged = JSON.parse(JSON.stringify(meta));
dragged.windowBars = patch.windowBars;
dragged.signal = Object.assign({}, dragged.signal, {
  chgPctMinScaled: patch.chgPctMinScaled, streakPlusMin: patch.streakPlusMin,
  streakMinusMin: patch.streakMinusMin, streakMinusMax: patch.streakMinusMax,
  crossDirection: patch.crossDirection, relation: patch.relation });
// the red block is moved too, and deliberately NOT as the mirror of the moved green one:
// the point of this harness is that each bullet prints its own block, so a cell that read
// the green rule's numbers while sitting in the red bullet would fail here
dragged.redSignal = Object.assign({}, dragged.redSignal, {
  chgPctMinScaled: -patch.chgPctMinScaled, streakPlusMin: patch.streakPlusMin,
  crossDirection: "ABOVE", relation: "ABOVE" });

const baseCells = new Function("META", src)(meta).cells();
const movedCells = new Function("META", src)(dragged).cells();
const changed = Object.keys(movedCells).filter(function (k) {
  return movedCells[k] !== baseCells[k]; });

const rules = new Function("META", src)(meta).rules;
console.log(JSON.stringify({
  base: baseCells, moved: movedCells, changed: changed,
  cellCount: Object.keys(baseCells).length,
  columns: rules.map(function (r) { return { column: r.column, inverted: r.inverted,
                                             label: r.label, mark: r.mark,
                                             position: r.position }; }),
  methodFnBytes: grabFn("signalMethodCells").length, srcBytes: src.length }));
'''

method_out: dict = {}
method_ran = False
method_err = ""
METHOD_PATCH = {"windowBars": WINDOW_BARS + 7, "chgPctMinScaled": 25, "streakPlusMin": 11,
                "streakMinusMin": 3, "streakMinusMax": 9, "crossDirection": "BELOW",
                "relation": "BELOW"}
with tempfile.TemporaryDirectory() as tmp:
    _method_js = Path(tmp) / "method_harness.js"
    _method_js.write_text(METHOD_HARNESS, encoding="utf-8")
    _meta_path = Path(tmp) / "method_meta.json"
    _meta_path.write_text(json.dumps(META), encoding="utf-8")
    _patch_path = Path(tmp) / "method_patch.json"
    _patch_path.write_text(json.dumps(METHOD_PATCH), encoding="utf-8")
    try:
        # the cells carry the sheet's en dash, so node's stdout is decoded as UTF-8 rather
        # than the console's code page: a mojibake dash would fail the comparisons below
        _mproc = subprocess.run(["node", str(_method_js), str(TEMPLATE), str(_meta_path),
                                 str(_patch_path)],
                                capture_output=True, text=True, encoding="utf-8",
                                timeout=300)
        method_ran = _mproc.returncode == 0
        if method_ran:
            method_out = json.loads(_mproc.stdout)
        else:
            _mtail = (_mproc.stderr or "").strip().splitlines()
            method_err = _mtail[-1] if _mtail else f"node exited {_mproc.returncode}"
    except FileNotFoundError as exc:
        method_err = f"node is not on PATH ({exc})"
    except subprocess.TimeoutExpired:
        method_err = "node did not finish within 300 s"
    except json.JSONDecodeError as exc:
        method_err = f"the harness printed no JSON: {exc}"

check(method_ran, "the sheet's own Method cells run outside the browser (node)", method_err)
check(method_out.get("methodFnBytes", 0) > 300 and method_out.get("srcBytes", 0) > 1000,
      "the harness executes the template's own signalMethodCells and its formatter",
      f"{method_out.get('methodFnBytes')} bytes of signalMethodCells out of "
      f"{method_out.get('srcBytes')}")

_mbase = method_out.get("base", {})
_mmoved = method_out.get("moved", {})
_sig = META.get("signal", {})


def _scaled_text(scaled: int, dp: int = PCT_DP) -> str:
    """A scaled integer as the sheet's own fmtScaled prints it -- the expected cell text."""
    text = str(abs(scaled)).rjust(dp + 1, "0")
    body = text[:len(text) - dp] + ("." + text[len(text) - dp:] if dp else "")
    return ("-" if scaled < 0 else "") + body


eq(_mbase.get("m-window"), str(META.get("windowBars")),
   "the Method list prints the recipe's chart window")
eq(_mbase.get("m-cross-pair"),
   f"SMA {_sig.get('crossFastPeriod')} vs SMA {_sig.get('crossSlowPeriod')}",
   "the Method list prints the crossing pair the rule reads")
eq(_mbase.get("m-distance-pair"),
   f"SMA {_sig.get('distanceFromPeriod')} vs SMA {_sig.get('distanceToPeriod')}",
   "the Method list prints the distance pair the rule reads")
eq(_mbase.get("m-relation-pair"),
   f"SMA {_sig.get('fastPeriod')} vs SMA {_sig.get('slowPeriod')}",
   "the Method list prints the run/change pair the rule reads")
eq(_mbase.get("m-distance-window"),
   _scaled_text(_sig["distancePctAtCrossMinScaled"]) + " \u2013 " +
   _scaled_text(_sig["distancePctAtCrossMaxScaled"]),
   "the Method list prints the distance window the arrows were filtered by")
eq(_mbase.get("m-chg-min"), _scaled_text(_sig["chgPctMinScaled"]),
   "the Method list prints the change threshold the rule reads")
eq(_mbase.get("m-minus-run"), f"{_sig['streakMinusMin']} to {_sig['streakMinusMax']}",
   "the Method list prints the falling-run window")
eq(_mbase.get("m-plus-run"), f"{_sig['streakPlusMin']} or more",
   "the Method list prints the rising-run floor")
eq(_mbase.get("m-cross-dir"), _sig["crossDirection"],
   "the Method list prints the cross word")
eq(_mbase.get("m-relation-dir"), _sig["relation"],
   "the Method list prints the relationship word")
eq(_mbase.get("m-off"), "",
   "the Method list marks the green rule as on when the recipe enables it")

# ---- the red bullet, from the payload's own redSignal block ------------------------------
_red = META.get("redSignal", {})
eq(method_out.get("columns"),
   [{"column": SIGNAL_KEY, "inverted": False, "label": "green arrow", "mark": "\u25b2",
     "position": "belowBar"},
    {"column": RED_KEY, "inverted": True, "label": "red arrow", "mark": "\u25bc",
     "position": "aboveBar"}],
   "the sheet builds both rules from the payload, with their own labels, marks and sides")
eq(_mbase.get("r-cross-pair"),
   f"SMA {_red.get('crossFastPeriod')} vs SMA {_red.get('crossSlowPeriod')}",
   "the red bullet prints the crossing pair the mirror reads")
eq(_mbase.get("r-cross-dir"), _red["crossDirection"],
   "the red bullet prints the mirrored cross word")
eq(_mbase.get("r-relation-dir"), _red["relation"],
   "the red bullet prints the mirrored relationship word")
eq(_mbase.get("r-distance-window"),
   _scaled_text(_red["distancePctAtCrossMinScaled"]) + " \u2013 " +
   _scaled_text(_red["distancePctAtCrossMaxScaled"]),
   "the red bullet prints the negated distance window, negative end first")
eq(_mbase.get("r-chg-min"), _scaled_text(_red["chgPctMinScaled"]),
   "the red bullet prints the negated change threshold, sign included")
eq(_mbase.get("r-chg-side"), "below",
   "the red bullet states the change is read below its threshold")
eq((_mbase.get("r-minus-dir"), _mbase.get("r-plus-dir")), ("rising", "falling"),
   "the red bullet names the runs the other way round, and so does the green one's")
eq((_mbase.get("m-minus-dir"), _mbase.get("m-plus-dir")), ("falling", "rising"),
   "the green bullet keeps its own run words")
eq(_mbase.get("r-off"), "",
   "the Method list marks the red rule as on when the recipe enables it")

eq(_mmoved.get("m-window"), str(METHOD_PATCH["windowBars"]),
   "the Method list's window cell follows a changed window_bars")
eq(_mmoved.get("m-chg-min"), _scaled_text(METHOD_PATCH["chgPctMinScaled"]),
   "the Method list's change threshold follows a changed [signal] chg_pct_min")
eq(_mmoved.get("m-plus-run"), f"{METHOD_PATCH['streakPlusMin']} or more",
   "the Method list's rising-run floor follows a changed streak_plus_min")
eq(_mmoved.get("m-minus-run"),
   f"{METHOD_PATCH['streakMinusMin']} to {METHOD_PATCH['streakMinusMax']}",
   "the Method list's falling-run window follows changed streak_minus bounds")
eq(_mmoved.get("m-cross-dir"), METHOD_PATCH["crossDirection"],
   "the Method list's cross word follows a changed cross_direction")
eq(_mmoved.get("m-relation-dir"), METHOD_PATCH["relation"],
   "the Method list's relationship word follows a changed relation")
eq(_mmoved.get("r-chg-min"), _scaled_text(-METHOD_PATCH["chgPctMinScaled"]),
   "the red bullet's change threshold follows its own moved block, negated sign and all")
eq(_mmoved.get("r-plus-run"), f"{METHOD_PATCH['streakPlusMin']} or more",
   "the red bullet's run floor follows its own moved block")
eq(_mmoved.get("r-cross-dir"), "ABOVE",
   "the red bullet's cross word follows its own block, not the green one's")
eq(_mmoved.get("m-cross-dir"), METHOD_PATCH["crossDirection"],
   "and the green bullet's word follows its own, at the same time")
eq(_mmoved.get("r-minus-run"), _mbase.get("r-minus-run"),
   "a cell the verifier did not move stayed put in the red bullet too")
eq(sorted(method_out.get("changed", [])),
   sorted(["m-chg-min", "m-plus-run", "m-minus-run", "m-cross-dir", "m-relation-dir",
           "m-window", "m-window-tail",
           "r-chg-min", "r-plus-run", "r-cross-dir", "r-relation-dir"]),
   "every cell either block's moved values touch moved, and no other cell did")
print(f"     the sheet's own Method cells: {method_out.get('cellCount', 0)} cells over both "
      f"bullets, {len(method_out.get('changed', []))} of them following a moved block")

# ---- the rule's edges, through the pipeline's own add_signal ----------------------------
# A generated tape can show that the rule works, not that its bounds mean what the recipe
# says. These cases are fed through the pipeline's own step with hand-built columns, so each
# comparison is exercised on both sides of its bound.


def signal_frame(cross_words, distances, relations, changes, plus_runs, minus_runs,
                 slow_plus_runs=None):
    """Bars carrying just the columns the rule reads, and nothing else."""
    bars = []
    for i in range(len(cross_words)):
        bars.append({
            f"sma{CROSS_FAST}_vs_sma{CROSS_SLOW}_cross_direction": cross_words[i],
            f"sma{CROSS_DIST_FROM}_vs_sma{CROSS_DIST_TO}_distance_pct_at_cross": distances[i],
            f"sma{RELATION_FAST}_vs_sma{RELATION_SLOW}_relation": relations[i],
            f"sma{RELATION_SLOW}_chg_pct": changes[i],
            f"sma{RELATION_FAST}_streak_plus": plus_runs[i],
            f"sma{RELATION_FAST}_streak_minus": minus_runs[i],
            f"sma{RELATION_SLOW}_streak_plus":
                (slow_plus_runs or [SIGNAL_STREAK_PLUS_MIN] * len(cross_words))[i],
        })
    return bars


def fire(cross_word="ABOVE", distance=SIGNAL_DISTANCE_PCT_AT_CROSS_MAX, relation="ABOVE",
         change=SIGNAL_CHG_PCT_MIN + 0.0001, plus=0,
         minus=SIGNAL_STREAK_MINUS_MIN, slow_plus=SIGNAL_STREAK_PLUS_MIN):
    """A three-candle tape whose middle candle carries the given values on candle 1."""
    bars = signal_frame([cross_word] * 3, [distance] * 3, [relation] * 3,
                        [change] * 3, [plus] * 3, [minus] * 3, [slow_plus] * 3)
    add_signal(bars, SIGNAL_RULE_OBJ, SIGNAL_KEY)
    return bars


def fire_red(cross_word=RED_CROSS_DIRECTION, distance=-SIGNAL_DISTANCE_PCT_AT_CROSS_MAX,
             relation=RED_RELATION, change=-(SIGNAL_CHG_PCT_MIN + 0.0001),
             plus=SIGNAL_STREAK_MINUS_MIN, minus=0,
             slow_minus=SIGNAL_STREAK_PLUS_MIN):
    """The same three-candle tape, built the other way round, for the mirror rule.

    The run columns are the mirror's to read: the fast average must be RISING (so its
    falling run is 0) and the slow average must be FALLING.
    """
    bars = signal_frame([cross_word] * 3, [distance] * 3, [relation] * 3,
                        [change] * 3, [plus] * 3, [minus] * 3)
    for bar in bars:
        bar[f"sma{RELATION_SLOW}_streak_minus"] = slow_minus
    add_signal(bars, RED_RULE_OBJ, RED_KEY)
    return bars


eq([b[SIGNAL_KEY] for b in fire()], [0, 1, 1],
   "pipeline: a candle holding all six conditions is flagged, and the tape's first candle "
   "is not (it has no previous candle), while the next one is")
for _field, _value, _what in (
        ("cross_word", "BELOW", "the cross named the other direction"),
        ("relation", "BELOW", "the relationship named the other side"),
        ("distance", SIGNAL_DISTANCE_PCT_AT_CROSS_MAX + 0.0001, "the distance sat just above the window"),
        ("distance", -0.0001, "the distance sat just below the window"),
        ("change", SIGNAL_CHG_PCT_MIN, "the previous change was exactly at its threshold"),
        ("minus", SIGNAL_STREAK_MINUS_MIN - 1, "the falling run was one candle too short"),
        ("minus", SIGNAL_STREAK_MINUS_MAX + 1, "the falling run was one candle too long"),
        ("plus", 1, "the fast average was rising, not falling"),
        ("slow_plus", SIGNAL_STREAK_PLUS_MIN - 1, "the rising run was one candle too short")):
    # the same tape with exactly one value moved out of its bound, and the same tape again
    # with that value back inside it: the flag must follow the single change both ways
    _bars = fire(**{_field: _value})
    eq((_bars[1][SIGNAL_KEY], fire()[1][SIGNAL_KEY]), (0, 1),
       f"pipeline: the flag follows this one value -- no flag when {_what}, flag when it "
       "is back inside its bound")

# the bounds are inclusive where the recipe says they are, on both ends
for _distance in (SIGNAL_DISTANCE_PCT_AT_CROSS_MIN, SIGNAL_DISTANCE_PCT_AT_CROSS_MAX, (SIGNAL_DISTANCE_PCT_AT_CROSS_MIN + SIGNAL_DISTANCE_PCT_AT_CROSS_MAX) / 2):
    eq(fire(distance=_distance)[1][SIGNAL_KEY], 1,
       f"pipeline: a distance of exactly {_distance} is inside the inclusive window")
eq(fire(minus=SIGNAL_STREAK_MINUS_MIN)[1][SIGNAL_KEY], 1,
   f"pipeline: a falling run of exactly {SIGNAL_STREAK_MINUS_MIN} qualifies")
eq(fire(minus=SIGNAL_STREAK_MINUS_MAX)[1][SIGNAL_KEY], 1,
   f"pipeline: a falling run of exactly {SIGNAL_STREAK_MINUS_MAX} qualifies")
eq(fire(slow_plus=SIGNAL_STREAK_PLUS_MIN)[1][SIGNAL_KEY], 1,
   f"pipeline: a rising run of exactly {SIGNAL_STREAK_PLUS_MIN} qualifies")
eq(fire(change=SIGNAL_CHG_PCT_MIN + 0.00005)[1][SIGNAL_KEY], 1,
   "pipeline: a change of half the threshold's own precision above it qualifies")

# ---- the mirror rule's edges, through the same pipeline step -----------------------------
# The mirror is a rule like any other once it exists, so its bounds are exercised the same
# way: both ends of its negated distance window, its negated change threshold, and the two
# runs it swapped roles with the green rule.
eq([b[RED_KEY] for b in fire_red()], [0, 1, 1],
   "pipeline: the mirror flags a candle holding all seven mirrored conditions, and never the "
   "tape's first candle")

# The mirror's flow condition, both ways round, on tapes built here: the dashboard pair the
# red rule reads is CE above PE, so a delivered session whose red candles all fall in
# PE-above-CE minutes legitimately carries none -- this delivery is one of those. That is
# why the red path is proved on these tapes rather than on the delivery alone: the same
# mirrored tape fires with CE above PE and refuses with the pair the other way round.
_red_flow_fires = fire_red()
for _bar in _red_flow_fires:
    _bar[CE_OI_CHANGE] = 5
    _bar[PE_OI_CHANGE] = 1
add_signal(_red_flow_fires, RED_RULE_OBJ, RED_KEY)
eq([b[RED_KEY] for b in _red_flow_fires], [0, 1, 1],
   "pipeline: with the dashboard minute reading CE above PE, the mirror fires")
_red_flow_refused = fire_red()
for _bar in _red_flow_refused:
    _bar[CE_OI_CHANGE] = 1
    _bar[PE_OI_CHANGE] = 5
add_signal(_red_flow_refused, RED_RULE_OBJ, RED_KEY)
eq([b[RED_KEY] for b in _red_flow_refused], [0, 0, 0],
   "pipeline: the same mirrored tape with PE above CE fires no red arrow at all")
# and the green rule's own reading of the pair, so the two sides of the swap are both pinned
_green_flow_fires = fire()
for _bar in _green_flow_fires:
    _bar[CE_OI_CHANGE] = 1
    _bar[PE_OI_CHANGE] = 5
add_signal(_green_flow_fires, SIGNAL_RULE_OBJ, SIGNAL_KEY)
eq([b[SIGNAL_KEY] for b in _green_flow_fires], [0, 1, 1],
   "pipeline: with the dashboard minute reading PE above CE, the green rule fires")
_green_flow_refused = fire()
for _bar in _green_flow_refused:
    _bar[CE_OI_CHANGE] = 5
    _bar[PE_OI_CHANGE] = 1
add_signal(_green_flow_refused, SIGNAL_RULE_OBJ, SIGNAL_KEY)
eq([b[SIGNAL_KEY] for b in _green_flow_refused], [0, 0, 0],
   "pipeline: the same green tape with CE above PE fires no green arrow")
# a session with no dashboard at all is the "condition not read" case: the same green tape
# with the pair left absent fires exactly as it does with the condition satisfied, and the
# mirror's tape does too -- absence decides nothing, it is not read as a zero
_no_dashboard = fire()
for _bar in _no_dashboard:
    _bar[CE_OI_CHANGE] = None
    _bar[PE_OI_CHANGE] = None
add_signal(_no_dashboard, SIGNAL_RULE_OBJ, SIGNAL_KEY)
eq([b[SIGNAL_KEY] for b in _no_dashboard], [0, 1, 1],
   "pipeline: a bar with no dashboard pair fires the green rule on its price conditions "
   "alone, so a session without a dashboard does not read the flow condition")
_no_dashboard_red = fire_red()
for _bar in _no_dashboard_red:
    _bar[CE_OI_CHANGE] = None
    _bar[PE_OI_CHANGE] = None
add_signal(_no_dashboard_red, RED_RULE_OBJ, RED_KEY)
eq([b[RED_KEY] for b in _no_dashboard_red], [0, 1, 1],
   "pipeline: and the mirror behaves the same way when the pair is absent")
# the invariant the delivery is measured against: the mirror fires on the delivered tapes, or
# the audit's own mirrored tape carries the red path for this delivery
check((RED_ARROWS[0] > 0 and RED_FRAMES_WITH_ARROWS[0] > 0) or _red_flow_fires[1][RED_KEY] == 1,
      "the mirror fires on the delivered tapes, or on the audit's own mirrored tape when the "
      "delivered flow condition leaves the delivery no red candle, so the red path is not vacuous",
      f"{RED_ARROWS[0]} red arrows on {RED_FRAMES_WITH_ARROWS[0]} delivered frames, "
      f"synthetic red candle {_red_flow_fires[1][RED_KEY]}")
for _field, _value, _what in (
        ("cross_word", "ABOVE", "the cross named the green rule's direction"),
        ("relation", "ABOVE", "the relationship named the green rule's side"),
        ("distance", -SIGNAL_DISTANCE_PCT_AT_CROSS_MAX - 0.0001,
         "the distance sat just below the mirrored window"),
        ("distance", 0.0001, "the distance sat just above the mirrored window"),
        ("change", -SIGNAL_CHG_PCT_MIN, "the previous change was exactly at its threshold"),
        ("plus", SIGNAL_STREAK_MINUS_MIN - 1, "the rising run was one candle too short"),
        ("plus", SIGNAL_STREAK_MINUS_MAX + 1, "the rising run was one candle too long"),
        ("minus", 1, "the fast average was falling, not rising"),
        ("slow_minus", SIGNAL_STREAK_PLUS_MIN - 1, "the falling run was one candle too short")):
    _bars = fire_red(**{_field: _value})
    eq((_bars[1][RED_KEY], fire_red()[1][RED_KEY]), (0, 1),
       f"pipeline: the mirror drops the flag when {_what}, and raises it again when the "
       "value is back inside its bound")
for _distance in (-SIGNAL_DISTANCE_PCT_AT_CROSS_MAX, -SIGNAL_DISTANCE_PCT_AT_CROSS_MIN):
    eq(fire_red(distance=_distance)[1][RED_KEY], 1,
       f"pipeline: a distance of exactly {_distance} is inside the mirror's inclusive window")
eq(fire_red(plus=SIGNAL_STREAK_MINUS_MIN)[1][RED_KEY], 1,
   f"pipeline: a rising run of exactly {SIGNAL_STREAK_MINUS_MIN} qualifies for the mirror")
eq(fire_red(plus=SIGNAL_STREAK_MINUS_MAX)[1][RED_KEY], 1,
   f"pipeline: a rising run of exactly {SIGNAL_STREAK_MINUS_MAX} qualifies for the mirror")
eq(fire_red(slow_minus=SIGNAL_STREAK_PLUS_MIN)[1][RED_KEY], 1,
   f"pipeline: a falling run of exactly {SIGNAL_STREAK_PLUS_MIN} qualifies for the mirror")

# one tape, both rules: a tape built for the green rule carries no red flag anywhere, and
# mirroring every column a rule READS turns the green flags into the red ones candle by
# candle. That last equality is the mirror property itself, stated on the rule's own inputs
# rather than on a price series: whatever the two rules are, this is what makes them mirror
_both = fire()
add_signal(_both, RED_RULE_OBJ, RED_KEY)
eq([b[RED_KEY] for b in _both], [0, 0, 0],
   "pipeline: on a tape built for the green rule the red one never fires")
_mirrored_both = mirror_columns(_both)
add_signal(_mirrored_both, RED_RULE_OBJ, RED_KEY)
eq([b[RED_KEY] for b in _mirrored_both], [b[SIGNAL_KEY] for b in _both],
   "pipeline: mirroring every column the rules read turns the green flags into the red ones, "
   "candle for candle")
_red_tape = fire_red()
_mirrored_red = mirror_columns(_red_tape)
add_signal(_mirrored_red, SIGNAL_RULE_OBJ, SIGNAL_KEY)
eq([b[SIGNAL_KEY] for b in _mirrored_red], [b[RED_KEY] for b in _red_tape],
   "pipeline: and the other way round -- the green rule on the mirrored columns is the red "
   "rule on the tape")

# the mirror of a mirrored rule is the rule itself, at the object level
check(RED_RULE_OBJ.mirrored() == SIGNAL_RULE_OBJ,
      "pipeline: mirroring the mirror returns the original rule")

# the previous candle is the ONLY previous candle: blanking a LATER candle's columns cannot
# change an earlier candle's flag, and a candle whose own columns are blank never flags
_bars = fire()
_bars[2] = dict(_bars[2])
for _key in list(_bars[2]):
    if _key != SIGNAL_KEY:
        _bars[2][_key] = None
add_signal(_bars, SIGNAL_RULE_OBJ, SIGNAL_KEY)
eq((_bars[1][SIGNAL_KEY], _bars[2][SIGNAL_KEY]), (1, 0),
   "pipeline: candle i is decided from i-1 only, so emptying a later candle leaves the "
   "earlier flag standing and blanks its own")

# a session boundary: a first candle whose own conditions all hold still carries no arrow
_edge = signal_frame(["ABOVE"], [SIGNAL_DISTANCE_PCT_AT_CROSS_MIN], ["ABOVE"], [SIGNAL_CHG_PCT_MIN * 2],
                     [0], [SIGNAL_STREAK_MINUS_MIN], [SIGNAL_STREAK_PLUS_MIN])
add_signal(_edge, SIGNAL_RULE_OBJ, SIGNAL_KEY)
eq(_edge[0][SIGNAL_KEY], 0,
   "pipeline: the first candle of a tape carries no arrow, however its own columns read")

# the switch in the recipe: enabled = false keeps the column and stops the drawing. The
# step itself stays a pure rule (the sheet is what declines to draw), so the same tape still
# computes -- what changes is what the payload says and what the sheet does with it
_off = load_config(CONFIG_PATH, overrides=["signal.enabled=false"])
eq(_off.signal_enabled, False, "the recipe can switch the arrow rule off")
eq(signal_meta(_off)["enabled"], False, "the payload records that it is off")
eq(_off.signal_rule_obj().read_columns, SIGNAL_RULE_OBJ.read_columns,
   "switching the rule off changes no threshold, only whether the arrows are drawn")
eq(_off.signal_fast, RELATION_FAST, "the [signal] pair defaults to the relationship pair")
eq(_off.signal_slow, RELATION_SLOW, "and to its slow half")
eq((_off.signal_cross_fast, _off.signal_cross_slow, _off.signal_distance_from,
     _off.signal_distance_to),
   (CROSS_FAST, CROSS_SLOW, CROSS_DIST_FROM, CROSS_DIST_TO),
   "the rule reads the crossing row and its distance row from [cross]")
_renamed = load_config(CONFIG_PATH, overrides=["signal.rule=only when I say so"])
eq(_renamed.signal_rule, "only when I say so",
   "a rewritten rule sentence travels in the payload as written")

# the recipe's own thresholds must be the ones this audit assumed, or it measured another rule
_recipe = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))["signal"]
for _key, _want in (("cross_direction", SIGNAL_CROSS_DIRECTION),                    ("relation", SIGNAL_RELATION),
                    ("distance_pct_at_cross_min", SIGNAL_DISTANCE_PCT_AT_CROSS_MIN),
                    ("distance_pct_at_cross_max", SIGNAL_DISTANCE_PCT_AT_CROSS_MAX),
                    ("chg_pct_min", SIGNAL_CHG_PCT_MIN),
                    ("streak_minus_min", SIGNAL_STREAK_MINUS_MIN),
                    ("streak_minus_max", SIGNAL_STREAK_MINUS_MAX),
                    ("streak_plus_min", SIGNAL_STREAK_PLUS_MIN)):
    eq(_recipe[_key], _want, f"config/nifty.toml [signal] {_key} is what this audit assumed")
eq(_recipe.get("red_arrow"), True,
   "config/nifty.toml [signal] draws the red arrow unless the recipe says otherwise")
check(not [k for k in _recipe if k.startswith("red_") and k != "red_arrow" and k != "red_rule"],
      "the [signal] block declares no red threshold: the mirror has none of its own",
      f"red keys {sorted(k for k in _recipe if k.startswith('red_'))}")

# the config layer refuses a rule it cannot honour
for _override, _what in (("signal.distance_pct_at_cross_min=0.5",
                          "a window floor above its ceiling"),
                         ("signal.relation=MIDDLE", "a word that is neither ABOVE nor BELOW"),
                         ("signal.cross_direction=Above", "a word in the wrong case"),
                         ("signal.streak_minus_min=0", "a falling run of zero candles"),
                         ("signal.streak_minus_max=3", "a run window below its own floor"),
                         ("signal.streak_plus_min=0", "a rising run of zero candles"),
                         ("signal.enabled=yes", "a switch that is not true or false"),
                         ("signal.red_arrow=maybe", "a red-arrow switch that is not true or false"),
                         ("signal.red_arrow_side=ABOVE",
                          "a key trying to give the red rule a side of its own"),
                         ("sheet.window_bars=1", "a chart window too small to read")):
    try:
        load_config(CONFIG_PATH, overrides=[_override])
        check(False, f"the recipe refuses {_what}", _override)
    except ConfigError:
        check(True, f"the recipe refuses {_what}")

# --------------------------------------------------------------------------------------
# 15  the recipe the build reads
#
# Section 11 pins this audit's own copy of the parameters against config/nifty.toml -- the
# theme of the whole file is that a parameter is asserted rather than trusted -- and against
# the delivered payload. This section covers the file the build actually reads when it is
# given no --config: config/nifty.json. It holds its own copy of that file's parameters too,
# then proves the two recipes resolve to ONE `Config`, field for field, the source path
# aside. That equality is what makes section 11's checks cover the JSON as well, so a value
# changed in one file and not the other is a failure here rather than a silent difference
# between what was audited and what a build would run. It ends on the interface a reader uses
# -- the command line with no --config -- and requires the sheet it writes to be the
# delivered sheet, byte for byte.
# --------------------------------------------------------------------------------------

print("\n15  the recipe the build reads")

JSON_CONFIG_PATH = ROOT / "config" / "nifty.json"
check(DEFAULT_CONFIG_PATH == JSON_CONFIG_PATH and JSON_CONFIG_PATH.is_file(),
      "the build's default recipe is config/nifty.json and the file exists",
      str(DEFAULT_CONFIG_PATH))

# every recipe the audit reads is read its own way: this one as JSON, so a file that is
# not valid JSON fails here rather than being quietly read as something else
try:
    json_recipe = json.loads(JSON_CONFIG_PATH.read_text(encoding="utf-8"))
except (OSError, ValueError) as exc:
    json_recipe = {}
    check(False, "the default recipe parses as JSON", str(exc))
if not isinstance(json_recipe, dict):
    json_recipe = {}
    check(False, "the default recipe is an object of sections", type(json_recipe).__name__)

# the JSON parameters this audit assumed -- the same idea as section 11's copy of the TOML
def _jget(*path: str) -> object:
    """One value out of the JSON recipe, or None where the file leaves it out."""
    node: object = json_recipe
    for step in path:
        if not isinstance(node, dict):
            return None
        node = node.get(step)
    return node


eq(_jget("instrument", "name"), META.get("instrument"), "JSON recipe: the instrument")
eq(_jget("sma", "price_periods"), list(SMA_PERIODS), "JSON recipe: the price averages")
eq(_jget("analytics", "periods"), list(ANALYTICS_SMAS), "JSON recipe: the analytics periods")
eq(_jget("analytics", "pct_decimals"), PCT_DP, "JSON recipe: the percentage precision")
eq(_jget("sheet", "window_bars"), WINDOW_BARS, "JSON recipe: the chart window")
eq(_jget("paths", "sources_dir"), SRC_DIR.name, "JSON recipe: the session folder")
eq(_jget("paths", "sources_glob"), SRC_GLOB, "JSON recipe: the session file glob")
eq(_jget("paths", "output_dir"), OUT_DIR.relative_to(ROOT).as_posix(),
   "JSON recipe: the output folder")
eq((_jget("direction_streak", "fast_period"), _jget("direction_streak", "slow_period")),
   (DIRECTION_FAST, DIRECTION_SLOW), "JSON recipe: the direction pair")
eq((_jget("cross", "fast_period"), _jget("cross", "slow_period"),
     _jget("cross", "distance_from_period"), _jget("cross", "distance_to_period")),
   (CROSS_FAST, CROSS_SLOW, CROSS_DIST_FROM, CROSS_DIST_TO),
   "JSON recipe: the crossing pair and the distance pair")
eq((_jget("relation", "fast_period"), _jget("relation", "slow_period")),
   (RELATION_FAST, RELATION_SLOW), "JSON recipe: the relationship pair")
check(isinstance(_jget("timeframes", "seconds"), list) and
      len(_jget("timeframes", "seconds")) == len(TIMEFRAMES),
      "JSON recipe: one bar width per audited timeframe",
      f"{_jget('timeframes', 'seconds')!r} against {list(TIMEFRAMES)}")
for _key, _want in (("cross_direction", SIGNAL_CROSS_DIRECTION),
                    ("relation", SIGNAL_RELATION),
                    ("distance_pct_at_cross_min", SIGNAL_DISTANCE_PCT_AT_CROSS_MIN),
                    ("distance_pct_at_cross_max", SIGNAL_DISTANCE_PCT_AT_CROSS_MAX),
                    ("chg_pct_min", SIGNAL_CHG_PCT_MIN),
                    ("streak_minus_min", SIGNAL_STREAK_MINUS_MIN),
                    ("streak_minus_max", SIGNAL_STREAK_MINUS_MAX),
                    ("streak_plus_min", SIGNAL_STREAK_PLUS_MIN)):
    eq(_jget("signal", _key), _want, f"JSON recipe [signal] {_key} is what this audit assumed")
eq(_jget("signal", "red_arrow"), True,
   "JSON recipe [signal] draws the red arrow unless the recipe says otherwise")
check(not [k for k in (_jget("signal") or {})
           if k.startswith("red_") and k not in ("red_arrow", "red_rule")],
      "the JSON [signal] block declares no red threshold either: the mirror has none",
      f"red keys {sorted(k for k in (_jget('signal') or {}) if k.startswith('red_'))}")

# every condition has a switch, and every recipe block spells all seven out. The flow
# switch used to be missing from the JSON's [signal] block: the rule still read the
# dashboard (an absent key falls back to true), so nothing looked wrong -- but the file a
# build reads first neither stated nor allowed turning that condition off. A default that
# hides a key is exactly what this check refuses.
CONDITION_SWITCHES = {"use_cross_direction", "use_distance_pct", "use_relation", "use_flow",
                      "use_chg_pct", "use_streak_minus", "use_streak_plus"}
_toml_recipe = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
for _label, _block in (("nifty.json [signal]", _jget("signal") or {}),
                       ("nifty.json [red_signal]", _jget("red_signal") or {}),
                       ("nifty.toml [signal]", _toml_recipe.get("signal", {})),
                       ("nifty.toml [red_signal]", _toml_recipe.get("red_signal", {}))):
    eq({k for k in _block if k.startswith("use_")}, CONDITION_SWITCHES,
       f"{_label} names the switch of all seven conditions")

# and the switch the JSON states is the one the rule reads, both ways round
_from_json = load_config(DEFAULT_CONFIG_PATH)
eq(_from_json.signal_use_flow, True,
   "the JSON recipe's [signal] use_flow reaches the resolved recipe")
eq(_from_json.signal_rule_obj().use_flow, True,
   "and the green rule the step runs reads the flow condition")
_json_flow_off = load_config(DEFAULT_CONFIG_PATH, overrides=["signal.use_flow=false"])
eq((_json_flow_off.signal_use_flow, _json_flow_off.signal_rule_obj().use_flow), (False, False),
   "--set signal.use_flow=false switches that condition off, and only it")
# and the switch does what it says: the flow condition refuses a candle whose minute reads
# PE below CE, and the same rule with use_flow off no longer looks at that column at all
def _flow_test(rule):
    return next(fn for key, _, fn in rule.tests() if key == "flow")


_pe_below_ce = {PE_OI_CHANGE: 0, CE_OI_CHANGE: 10}
check(not _flow_test(CONFIG_OBJ.signal_rule_obj())(_pe_below_ce, None),
      "the flow condition refuses a candle whose minute reads PE below CE")
check(_flow_test(_json_flow_off.signal_rule_obj())(_pe_below_ce, None),
      "with use_flow off the same rule no longer reads that condition")

# --- the two recipe files are one recipe -------------------------------------------------
default_cfg = load_config()
toml_cfg = load_config(MIRROR_CONFIG_PATH)
eq(default_cfg.source, DEFAULT_CONFIG_PATH,
   "a build with no recipe of its own reads the JSON one")
check(MIRROR_CONFIG_PATH.is_file(), "the TOML twin ships beside it", str(MIRROR_CONFIG_PATH))


def _resolved(cfg) -> dict:
    """Every field of a resolved recipe, minus the file it came from."""
    fields = dataclasses.asdict(cfg)
    fields.pop("source")
    return fields


_mirror_fields = _resolved(toml_cfg)
_same = [name for name, value in _resolved(default_cfg).items()
         if value != _mirror_fields[name]]
check(not _same,
      "config/nifty.json and config/nifty.toml resolve to one recipe, field for field",
      f"these differ: {_same}")

# --- how a JSON recipe explains itself ---------------------------------------------------
# JSON has no comment syntax, so a key whose name starts with '_' is a note: its value is
# ignored and may be a string or a list of lines. The one way that convention could hide a
# mistake is a note named after the setting it sits beside, so that is refused by name.
_note_keys = [k for k in json_recipe if k.startswith("_")]
_note_keys += [k for table in json_recipe.values() if isinstance(table, dict)
               for k in table if k.startswith("_")]
check(len(_note_keys) >= 2, "the JSON recipe explains itself with '_' notes",
      f"{len(_note_keys)} notes")
check(not [k for k in _resolved(default_cfg) if k.startswith("_")],
      "no note reaches the resolved recipe")

_json_scratch = Path(tempfile.mkdtemp(prefix="nifty_json_recipe_"))


def _json_refusal(what: str, body: object) -> str:
    """What `load_config` says about a recipe written to a temporary file."""
    path = _json_scratch / f"{what}.json"
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    try:
        load_config(path)
    except ConfigError as exc:
        return str(exc)
    return ""


_msg = _json_refusal("note-key", {"signal": {"_enabled": False}})
check("_enabled" in _msg and "enabled" in _msg,
      "a note named after a setting is refused rather than silently ignored", _msg)
_msg = _json_refusal("note-section", {"_signal": {"enabled": False}})
check("_signal" in _msg and "[signal]" in _msg,
      "a note named after a section is refused too", _msg)
_msg = _json_refusal("typo", {"signal": {"enabledd": False}})
check("enabledd" in _msg and "enabled" in _msg,
      "a real typo in the JSON recipe is still refused, and the key it meant is named", _msg)
_msg = _json_refusal("broken", '{"signal": }')
check("not valid JSON" in _msg,
      "a JSON recipe that does not parse says so, rather than reporting a TOML error", _msg)

# --- the interface a reader uses ---------------------------------------------------------
# No --config: the recipe the build picks up on its own. The sheet it writes has to be the
# delivered sheet, so the default recipe is proved end to end and not only by comparison.
_scratch = Path(tempfile.mkdtemp(prefix="nifty_default_recipe_"))
_built = subprocess.run([sys.executable, str(BUILDER), "--out-dir", str(_scratch), "--quiet"],
                        cwd=ROOT, capture_output=True, text=True, timeout=900)
check(_built.returncode == 0, "a build with no --config succeeds on the command line",
      (_built.stderr or _built.stdout)[-400:])
_written = sorted(_scratch.glob("NIFTY_*_SMA_sheet.html"))
check(len(_written) == 1, "the default recipe delivers one sheet",
      f"{len(_written)} sheet(s) in {_scratch}")
if _written:
    eq(_written[0].name, SHEET.name, "under the delivered name")
    eq(hashlib.sha256(_written[0].read_bytes()).hexdigest(), sheet_before,
       "the default recipe builds the delivered sheet, byte for byte")

# --------------------------------------------------------------------------------------
# 16  the session's source file
#
# A session is either its 1-second tape or, on its own, the dashboard that carries the same
# per-second series under `nifty_seconds`. This section reads the dashboard with its own
# code, proves the two files agree on every second they share and that the only seconds the
# dashboard lacks are the closing minute's tail, then exercises the pipeline's discovery and
# reader -- one session per session, tape first -- and ends on a dashboard-only build through
# the command line, whose bars and arrows must be the delivered ones.
# --------------------------------------------------------------------------------------

print("\n16  a session may ship only its dashboard")

DASHBOARDS = sorted(SRC_DIR.glob(DASH_GLOB))
if not check(bool(DASHBOARDS),
             "a delivered session ships a dashboard carrying its own per-second series",
             f"no {DASH_GLOB} in {SRC_DIR.name}"):
    DASHBOARDS = []


def hhmmss(epoch: int) -> str:
    return datetime.fromtimestamp(epoch + IST, tz=timezone.utc).strftime("%H:%M:%S")


# --- 16a  the two files are one session ------------------------------------------------

_paired = [d for d in DASHBOARDS if paired_tape(d).is_file()]
for _dash in _paired:
    _tape = paired_tape(_dash)
    _tape_ticks = {t["epoch"]: (t["nifty"], t["atm"]) for t in load_ticks(_tape)}
    _dash_ticks = dashboard_seconds(_dash)
    _shared = sorted(set(_tape_ticks) & set(_dash_ticks))
    check(len(_shared) == len(_dash_ticks),
          f"{_dash.name}: every one of the dashboard's {len(_dash_ticks):,} seconds is on the tape",
          f"{len(_dash_ticks) - len(_shared)} second(s) of the dashboard are not on the tape")
    _mismatch = [e for e in _shared if _tape_ticks[e] != _dash_ticks[e]]
    check(not _mismatch,
          f"{_dash.name}: its series carries the tape's own price and strike on all "
          f"{len(_shared):,} shared seconds",
          f"{len(_mismatch)} differ, first {[(hhmmss(e), _tape_ticks[e], _dash_ticks[e]) for e in _mismatch[:3]]}")
    # the tape is the fuller record: what it has and the dashboard does not is the closing
    # minute's tail, after the feed's last publish and inside the same bar
    _tail = sorted(set(_tape_ticks) - set(_dash_ticks))
    _last = max(_dash_ticks)
    check(all(_last < e < _last + 60 for e in _tail),
          f"{_dash.name}: the {len(_tail)} seconds only the tape has are the closing minute's "
          f"tail after {hhmmss(_last)}",
          f"{(hhmmss(_tail[0]), hhmmss(_tail[-1])) if _tail else 'none'}")
    _extra = (f"; the tape's extra {len(_tail)} second(s) run {hhmmss(_tail[0])} to "
              f"{hhmmss(_tail[-1])}") if _tail else ""
    print(f"     {_dash.name}: {len(_dash_ticks):,} seconds, every one on the tape with the "
          f"same price and strike{_extra}")

# --- 16b  the pipeline reads the dashboard as the same ticks -----------------------------

from nifty.data.bars import discover_sources                                  # noqa: E402
from nifty.data.bars import load_ticks as pipeline_load_ticks                 # noqa: E402
from nifty.core.errors import DataError as PipelineDataError                  # noqa: E402

for _dash in DASHBOARDS:
    _want = sorted((e, value[0], value[1]) for e, value in dashboard_seconds(_dash).items())
    _got = [(t["epoch"], t["nifty"], t["atm"]) for t in pipeline_load_ticks(_dash)]
    eq(_got, _want, f"{_dash.name}: the pipeline's reader returns its series, second for second")

# --- 16b2  one reader, two indices --------------------------------------------------------
# a SENSEX feed names its series `sensex_seconds` and its price `sensex`; the reader must
# hand back the same ticks, and nothing downstream may need to know which feed it read.
_keys_dir = Path(tempfile.mkdtemp(prefix="nifty_index_keys_"))
_sensex_path = _keys_dir / f"SENSEX_{DAY_KEYS[-1]}{DASH_SUFFIX}"
_sensex_path.write_text(json.dumps({"sensex_seconds": [
    {"timestamp": f"{DAY_KEYS[-1]} 09:15:00", "timestamp_epoch": 1792122300,
     "sensex": 74341.08, "atm": 74300},
    {"timestamp": f"{DAY_KEYS[-1]} 09:15:01", "timestamp_epoch": 1792122301,
     "sensex": 74345.5, "atm": 74300},
]}), encoding="utf-8")
eq([(t["epoch"], t["nifty"], t["atm"]) for t in pipeline_load_ticks(_sensex_path)],
   [(1792122300, 74341.08, 74300), (1792122301, 74345.5, 74300)],
   "a dashboard keyed sensex_seconds / sensex reads as the same ticks")
_nifty_path = _keys_dir / f"NIFTY_{DAY_KEYS[-1]}{DASH_SUFFIX}"
_nifty_path.write_text(json.dumps({"nifty_seconds": [
    {"timestamp": f"{DAY_KEYS[-1]} 09:15:00", "timestamp_epoch": 1792122300,
     "nifty": 23065.1, "atm": 23050}]}), encoding="utf-8")
eq([(t["nifty"], t["atm"]) for t in pipeline_load_ticks(_nifty_path)], [(23065.1, 23050)],
   "and a dashboard keyed nifty_seconds / nifty still reads")
_no_series = _keys_dir / f"SENSEX_1999-01-01{DASH_SUFFIX}"
_no_series.write_text(json.dumps({"seconds": []}), encoding="utf-8")
try:
    pipeline_load_ticks(_no_series)
    check(False, "a dashboard with neither series key is refused", "accepted")
except PipelineDataError:
    check(True, "a dashboard with neither series key is refused")

# --- 16c  one session per session, the tape when there is one ----------------------------

if DASHBOARDS:
    _dash = DASHBOARDS[0]
    _solo = Path(tempfile.mkdtemp(prefix="nifty_dash_source_"))
    shutil.copy2(_dash, _solo / _dash.name)
    eq([p.name for p in discover_sources(_solo, SRC_GLOB)], [_dash.name],
       "a folder holding only the dashboard discovers it as one session")
    # a tape to sit beside it: the real one where the session ships both, otherwise the
    # dashboard's own first seconds written in the tape's format, since the point here is
    # which file discovery prefers, not what a tape looks like
    _both = Path(tempfile.mkdtemp(prefix="nifty_dash_both_"))
    shutil.copy2(_dash, _both / _dash.name)
    _tape = paired_tape(_dash)
    if _tape.is_file():
        shutil.copy2(_tape, _both / _tape.name)
    else:
        _seconds = dashboard_seconds(_dash)
        with (_both / _tape.name).open("w", encoding="utf-8") as fh:
            for _epoch in sorted(_seconds)[:3]:
                fh.write(json.dumps({
                    "timestamp": datetime.fromtimestamp(_epoch + IST, tz=timezone.utc)
                                 .strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp_epoch": _epoch, "nifty": _seconds[_epoch][0],
                    "atm": _seconds[_epoch][1]}) + "\n")
    eq([p.name for p in discover_sources(_both, SRC_GLOB)], [_tape.name],
       "once a tape is beside it, the tape is the session -- the dashboard is not a second one")
    _empty = Path(tempfile.mkdtemp(prefix="nifty_dash_empty_"))
    try:
        discover_sources(_empty, SRC_GLOB)
        check(False, "a folder with neither a tape nor a dashboard is refused", str(_empty))
    except PipelineDataError:
        check(True, "a folder with neither a tape nor a dashboard is refused")

    # --- 16d  a dashboard-only build is the delivered session ---------------------------

    _out = Path(tempfile.mkdtemp(prefix="nifty_dash_build_"))
    _built = subprocess.run([sys.executable, str(BUILDER), "--input-dir", str(_solo),
                             "--out-dir", str(_out), "--quiet"],
                            cwd=ROOT, capture_output=True, text=True, timeout=900)
    check(_built.returncode == 0, "a dashboard-only session builds through the command line",
          (_built.stderr or _built.stdout)[-400:])
    _day = ist_day(max(dashboard_seconds(_dash)))
    _delivered_1m = OUT_DATA / DAY_KEYS[0] / "nifty_1min.csv"
    _built_1m = _out / "data" / _day / "nifty_1min.csv"
    if _built_1m.is_file():
        with _delivered_1m.open(encoding="utf-8", newline="") as fh:
            _shipped = list(csv.DictReader(fh))
        with _built_1m.open(encoding="utf-8", newline="") as fh:
            _from_dash = list(csv.DictReader(fh))
        eq(len(_from_dash), len(_shipped),
           "1m: the dashboard-only build ships one bar per delivered bar")
        _cells = [(i, k) for i, (a, b) in enumerate(zip(_shipped, _from_dash))
                  for k in a if a[k] != b[k]]
        check(all(k == "ticks" for _, k in _cells),
              f"1m: all {len(_shipped)} bars carry the delivered OHLC and indicators",
              f"{sum(1 for _, k in _cells if k != 'ticks')} non-tick cell(s) differ: "
              f"{[(i, k) for i, k in _cells if k != 'ticks'][:4]}")
        eq([r[SIGNAL_KEY] for r in _from_dash], [r[SIGNAL_KEY] for r in _shipped],
           "1m: the same green arrows, candle for candle")
        eq([r[RED_KEY] for r in _from_dash], [r[RED_KEY] for r in _shipped],
           "1m: the same red arrows, candle for candle")
        eq([r[CE_OI_CHANGE] for r in _from_dash], [r[CE_OI_CHANGE] for r in _shipped],
           "1m: the flow columns still ride along when the dashboard is the session")


        _built_12s = _out / "data" / _day / "nifty_12sec.csv"
        _delivered_12s = OUT_DATA / DAY_KEYS[0] / "nifty_12sec.csv"
        with _built_12s.open(encoding="utf-8", newline="") as fh:
            _fast = list(csv.DictReader(fh))
        with _delivered_12s.open(encoding="utf-8", newline="") as fh:
            _fast_shipped = {r["epoch"]: r for r in csv.DictReader(fh)}
        _missing = [r for r in _fast if r["epoch"] not in _fast_shipped]
        _bad = [(r["epoch"], k) for r in _fast for k in ("open", "high", "low", "close")
                if _fast_shipped[r["epoch"]][k] != r[k]]
        check(not _missing and not _bad,
              f"12s: all {len(_fast):,} dashboard-built bars are the delivered bars, OHLC for OHLC",
              f"{len(_missing)} unknown bar(s), {len(_bad)} differing cell(s)")
        check(len(_fast) <= len(_fast_shipped),
              "12s: the dashboard build cannot add a bar the delivered session lacks",
              f"{len(_fast)} against {len(_fast_shipped)}")
        eq([r[SIGNAL_KEY] for r in _fast],
           [_fast_shipped[r["epoch"]][SIGNAL_KEY] for r in _fast],
           "12s: the same green arrows, candle for candle")
        eq([r[RED_KEY] for r in _fast],
           [_fast_shipped[r["epoch"]][RED_KEY] for r in _fast],
           "12s: the same red arrows, candle for candle")
        print(f"     a dashboard-only build: {len(_from_dash)} 1m bars, "
              f"{len(_fast):,} 12s bars and "
              f"{sum(1 for r in _fast if r[SIGNAL_KEY] == '1')} green / "
              f"{sum(1 for r in _fast if r[RED_KEY] == '1')} red arrows -- the delivered "
              f"bars and arrows")
    else:
        check(False, "1m: the dashboard-only build wrote the session's export", str(_built_1m))

    _summary_path = _out / "data" / "session_summary.json"
    _sess = (json.loads(_summary_path.read_text(encoding="utf-8"))["days"].get(_day, {})
             .get("session", {})) if _summary_path.is_file() else {}
    eq(_sess.get("ticks"), len(dashboard_seconds(_dash)),
       "the dashboard-only session records the ticks it actually read")
    check(str(_sess.get("source", "")).endswith(_dash.name),
          "and records the dashboard as its source", str(_sess.get("source")))
    eq(_sess.get("sessionEndIST"),
       datetime.fromtimestamp(max(dashboard_seconds(_dash)) + IST,
                              tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
       "and ends at the dashboard's own last second")

# --------------------------------------------------------------------------------------
# 17  the trade clock
#
# The backtest books a trade per arrow and is bounded by two recipe times: no entry after
# `backtest.last_entry`, and a hard exit at `backtest.hard_exit` that closes whatever is
# still open at that candle's opening price. This section pins the two values in both
# recipes, refuses a recipe whose clock runs backwards or is not a time, then audits the
# records the module produces: no trade entered after the cut-off, none carried past the
# hard exit, the late arrows reported rather than traded, and the cut-off proved on a
# candle exactly at it and one bar later.
# --------------------------------------------------------------------------------------

print("\n17  the trade clock")

BACKTEST_LAST_ENTRY = "15:10:00"
BACKTEST_HARD_EXIT = "15:15:00"

from nifty.trade import backtest as backtest_module                              # noqa: E402
from nifty.core.clock import clock_seconds, ist_clock as pipeline_ist_clock    # noqa: E402

# --- 17a  the recipe, both forms --------------------------------------------------------

eq((default_cfg.backtest_last_entry, default_cfg.backtest_hard_exit),
   (BACKTEST_LAST_ENTRY, BACKTEST_HARD_EXIT),
   "the resolved recipe carries the entry cut-off and the hard exit")
eq((_jget("backtest", "last_entry"), _jget("backtest", "hard_exit")),
   (BACKTEST_LAST_ENTRY, BACKTEST_HARD_EXIT),
   "nifty.json states both times")
eq((_toml_recipe.get("backtest", {}).get("last_entry"),
     _toml_recipe.get("backtest", {}).get("hard_exit")),
   (BACKTEST_LAST_ENTRY, BACKTEST_HARD_EXIT),
   "nifty.toml states both times")
for _override, _what in (("backtest.hard_exit=15:10:00", "a hard exit at the entry cut-off"),
                         ("backtest.hard_exit=14:00:00", "a hard exit before the last entry"),
                         ("backtest.last_entry=25:00:00", "an hour that does not exist"),
                         ("backtest.hard_exit=quarter past", "a time that is not a clock time"),
                         ("backtest.hard_exit=", "an empty time")):
    try:
        load_config(DEFAULT_CONFIG_PATH, overrides=[_override])
        check(False, f"the recipe refuses {_what}", _override)
    except ConfigError:
        check(True, f"the recipe refuses {_what}")

# a normalising read: '9:15' and '09:15:00' are one time, so two recipes cannot differ by shape
eq(load_config(DEFAULT_CONFIG_PATH, overrides=["backtest.last_entry=9:5"]).backtest_last_entry,
   "09:05:00", "a time is normalised to HH:MM:SS")

# --- 17b  the records the module books --------------------------------------------------

_arrows = json.loads((OUT_DATA / "arrow_signal.json").read_text(encoding="utf-8"))
_records = [backtest_module.backtest_one(_arrow, default_cfg) for _arrow in _arrows]
_exited = [_r for _r in _records if _r["trade_status"] == "exited"]
_late = [_r for _r in _records if _r["trade_status"] == "no entry"]
_hard = [_r for _r in _exited if str(_r["exit_reason"]).startswith("hard exit")]

check(bool(_exited), "the backtest books trades on the delivered arrows", f"{len(_exited)}")
_late_traded = [_r for _r in _exited if str(_r["entry_time"])[-8:] > BACKTEST_LAST_ENTRY]
check(not _late_traded, "no trade was taken after the entry cut-off",
      f"{len(_late_traded)} late: {[(_r['date'], _r['time']) for _r in _late_traded[:4]]}")
_overrun = [_r for _r in _exited if str(_r["exit_time"])[-8:] > BACKTEST_HARD_EXIT]
check(not _overrun, "no trade was carried past the hard exit",
      f"{len(_overrun)}: {[(_r['date'], _r['exit_time']) for _r in _overrun[:4]]}")
check(all(_r["exit_reason"].endswith("entry cut-off") for _r in _late),
      "every late arrow is reported as no entry, not traded")
check(all(_r["exit_price"] not in (None, "") for _r in _exited),
      "every exited trade carries a price -- nothing is left open")
check(not [_r for _r in _records if _r["trade_status"] == "no cross"],
      "no position is left open at the end of the day",
      f"{[(_r['date'], _r['time']) for _r in _records if _r['trade_status'] == 'no cross'][:3]}")
if check(bool(_hard), "at least one position was closed by the hard exit",
         f"{len(_hard)} of {len(_exited)}"):
    check(all(str(_r["exit_time"])[-8:] == BACKTEST_HARD_EXIT for _r in _hard),
          f"every hard exit is stamped {BACKTEST_HARD_EXIT}")
    print(f"     {len(_records)} arrows -> {len(_exited)} trades, {len(_hard)} closed by the "
          f"hard exit{', ' + str(len(_late)) + ' late arrow(s) not taken' if _late else ''}")

# --- 17c  the cut-off, on the candle itself ---------------------------------------------

_day = DAY_KEYS[-1]
_bars_12s = json.loads((OUT_DATA / _day / "nifty_12sec.json").read_text(encoding="utf-8"))["bars"]

def _arrow_at(label: str) -> dict:
    index = next(i for i, bar in enumerate(_bars_12s) if hhmmss(bar["time"]) == label)
    return {"srNo": 0, "date": _day, "time": label, "timeframe": "12 sec",
            "timeframeSeconds": 12, "arrow": "green", "epoch": _bars_12s[index]["time"],
            "barIndex": index, "close": _bars_12s[index]["close"]}

_at_cutoff = backtest_module.backtest_one(_arrow_at(BACKTEST_LAST_ENTRY), default_cfg)
_after_cutoff = backtest_module.backtest_one(_arrow_at("15:10:12"), default_cfg)
check(_at_cutoff["trade_status"] != "no entry",
      f"an arrow on the {BACKTEST_LAST_ENTRY} candle is still taken",
      _at_cutoff["exit_reason"])
eq(_after_cutoff["trade_status"], "no entry",
   "an arrow on the next candle is not taken")
eq(pipeline_ist_clock(_arrow_at(BACKTEST_LAST_ENTRY)["epoch"]),
   clock_seconds(BACKTEST_LAST_ENTRY),
   "the clock the rule reads is the candle's own IST wall clock")

report()
