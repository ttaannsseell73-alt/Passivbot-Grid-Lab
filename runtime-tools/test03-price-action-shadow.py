#!/usr/bin/env python3
"""GRID V2 TEST #03: Direction veto + causal Price Action quality gate.

Read-only evaluator. It consumes Passivbot's local 1h OHLCV cache and never
connects to an exchange or creates orders.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np

HERE = Path(__file__).resolve().parent
TEST02_PATH = HERE / "test02-direction-shadow.py"
spec = importlib.util.spec_from_file_location("gridv2_test02_direction", TEST02_PATH)
test02 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = test02
assert spec.loader is not None
spec.loader.exec_module(test02)

HOUR_MS = test02.HOUR_MS
REQUIRED_FIELDS = test02.REQUIRED_FIELDS


@dataclass(frozen=True)
class PriceActionDecision:
    direction: str
    score: float
    aligned_votes: int
    structure: float
    breakout_retest: float
    liquidity_sweep: float
    rejection: float
    compression_expansion: float
    passed: bool


def _safe_div(a: float, b: float) -> float:
    return a / b if b and math.isfinite(b) else 0.0


def _atr_like(data: np.ndarray, start: int, end: int) -> float:
    if end <= start:
        return 0.0
    h = data["h"][start:end].astype(np.float64)
    l = data["l"][start:end].astype(np.float64)
    c = data["c"][start:end].astype(np.float64)
    if len(c) < 2:
        return 0.0
    prev = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    vals = tr[np.isfinite(tr) & (tr >= 0.0)]
    return float(np.mean(vals)) if len(vals) else 0.0


def _sign_for(direction: str) -> int:
    return 1 if direction == "LONG" else -1


def pa_components(data: np.ndarray, i: int, direction: str) -> dict[str, float]:
    if i < 30:
        return {k: 0.0 for k in ("structure", "breakout_retest", "liquidity_sweep", "rejection", "compression_expansion")}

    o = data["o"].astype(np.float64)
    h = data["h"].astype(np.float64)
    l = data["l"].astype(np.float64)
    c = data["c"].astype(np.float64)

    s = _sign_for(direction)
    close = float(c[i])
    if not (close > 0.0 and np.isfinite(close)):
        return {k: 0.0 for k in ("structure", "breakout_retest", "liquidity_sweep", "rejection", "compression_expansion")}

    # 1) Market structure: compare recent swing regime and close location.
    hi_recent = float(np.max(h[i-5:i+1]))
    lo_recent = float(np.min(l[i-5:i+1]))
    hi_prev = float(np.max(h[i-11:i-5]))
    lo_prev = float(np.min(l[i-11:i-5]))
    long_structure = 0.5 * float(hi_recent > hi_prev) + 0.5 * float(lo_recent > lo_prev)
    short_structure = 0.5 * float(hi_recent < hi_prev) + 0.5 * float(lo_recent < lo_prev)
    structure = long_structure - short_structure

    # 2) Breakout/retest: breakout in last 3 bars, then hold/retest prior 20-bar boundary.
    br = 0.0
    for j in range(max(20, i - 2), i + 1):
        prior_hi = float(np.max(h[j-20:j]))
        prior_lo = float(np.min(l[j-20:j]))
        if direction == "LONG":
            broke = float(c[j]) > prior_hi
            held = float(l[i]) <= prior_hi * 1.003 and float(c[i]) >= prior_hi
            if broke and held:
                br = 1.0
                break
        else:
            broke = float(c[j]) < prior_lo
            held = float(h[i]) >= prior_lo * 0.997 and float(c[i]) <= prior_lo
            if broke and held:
                br = -1.0
                break

    # 3) Liquidity sweep: wick beyond prior 10-bar extreme, close back inside.
    prior10_hi = float(np.max(h[i-10:i]))
    prior10_lo = float(np.min(l[i-10:i]))
    sweep = 0.0
    if float(l[i]) < prior10_lo and float(c[i]) > prior10_lo:
        sweep += 1.0
    if float(h[i]) > prior10_hi and float(c[i]) < prior10_hi:
        sweep -= 1.0

    # 4) Rejection candle: directional wick/body geometry.
    rng = max(float(h[i] - l[i]), close * 1e-8)
    body = abs(float(c[i] - o[i]))
    upper = float(h[i] - max(o[i], c[i]))
    lower = float(min(o[i], c[i]) - l[i])
    rejection = 0.0
    if lower / rng >= 0.45 and body / rng <= 0.5 and c[i] >= o[i]:
        rejection += min(1.0, lower / rng)
    if upper / rng >= 0.45 and body / rng <= 0.5 and c[i] <= o[i]:
        rejection -= min(1.0, upper / rng)

    # 5) Compression -> expansion: recent 6h ATR compressed vs prior 24h, current TR expands.
    atr6 = _atr_like(data, i-6, i)
    atr24 = _atr_like(data, i-30, i-6)
    prev_close = float(c[i-1])
    tr_now = max(float(h[i] - l[i]), abs(float(h[i] - prev_close)), abs(float(l[i] - prev_close)))
    ce = 0.0
    compressed = atr24 > 0.0 and atr6 <= 0.72 * atr24
    expanded = atr6 > 0.0 and tr_now >= 1.6 * atr6
    if compressed and expanded:
        if c[i] > o[i]:
            ce = 1.0
        elif c[i] < o[i]:
            ce = -1.0

    # Convert to requested direction's alignment [-1,+1].
    return {
        "structure": float(np.clip(s * structure, -1.0, 1.0)),
        "breakout_retest": float(np.clip(s * br, -1.0, 1.0)),
        "liquidity_sweep": float(np.clip(s * sweep, -1.0, 1.0)),
        "rejection": float(np.clip(s * rejection, -1.0, 1.0)),
        "compression_expansion": float(np.clip(s * ce, -1.0, 1.0)),
    }


def pa_decision(data: np.ndarray, i: int, direction: str, threshold: float = 0.24, min_votes: int = 2) -> PriceActionDecision:
    comp = pa_components(data, i, direction)
    weights = {
        "structure": 0.30,
        "breakout_retest": 0.20,
        "liquidity_sweep": 0.20,
        "rejection": 0.15,
        "compression_expansion": 0.15,
    }
    score = sum(weights[k] * comp[k] for k in weights)
    votes = sum(1 for v in comp.values() if v >= 0.35)
    strong_opposition = sum(1 for v in comp.values() if v <= -0.35)
    passed = bool(score >= threshold and votes >= min_votes and strong_opposition <= 1)
    return PriceActionDecision(
        direction=direction,
        score=float(score),
        aligned_votes=int(votes),
        passed=passed,
        **comp,
    )


def parse_audit(value: str) -> tuple[str, str, int]:
    symbol, expected, iso = value.split(",", 2)
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return symbol.upper(), expected.upper(), int(dt.timestamp() * 1000)


def safe_num(x: float):
    return float(x) if math.isfinite(float(x)) else None


def summarize(samples: list[dict], horizons: Iterable[int], round_trip_cost: float) -> dict:
    out = {}
    for h in horizons:
        vals = np.asarray([s[f"signed_{h}h"] for s in samples], dtype=np.float64)
        vals = vals[np.isfinite(vals)]
        if not len(vals):
            out[f"{h}h"] = {"events": 0}
            continue
        net = vals - round_trip_cost
        q01 = float(np.quantile(vals, 0.01))
        q99 = float(np.quantile(vals, 0.99))
        trimmed = vals[(vals >= q01) & (vals <= q99)]
        out[f"{h}h"] = {
            "events": int(len(vals)),
            "gross_hit_rate": float(np.mean(vals > 0.0)),
            "net_hit_rate": float(np.mean(net > 0.0)),
            "mean_gross_signed_return": float(np.mean(vals)),
            "median_gross_signed_return": float(np.median(vals)),
            "trimmed_1pct_mean_gross_signed_return": float(np.mean(trimmed)) if len(trimmed) else None,
            "mean_net_signed_return": float(np.mean(net)),
            "zero_return_rate": float(np.mean(np.abs(vals) <= 1e-12)),
            "p10_gross_signed_return": float(np.quantile(vals, 0.10)),
            "p90_gross_signed_return": float(np.quantile(vals, 0.90)),
        }
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="caches/ohlcv/binance/1h")
    p.add_argument("--direction-threshold", type=float, default=0.18)
    p.add_argument("--pa-threshold", type=float, default=0.24)
    p.add_argument("--min-pa-votes", type=int, default=2)
    p.add_argument("--min-history", type=int, default=48)
    p.add_argument("--step-hours", type=int, default=4)
    p.add_argument("--round-trip-cost-bps", type=float, default=4.0)
    p.add_argument("--audit", action="append", default=[])
    p.add_argument("--json-out")
    args = p.parse_args()

    root = Path(args.root)
    dirs = sorted([d for d in root.iterdir() if d.is_dir() and d.name.endswith("_USDT:USDT")])
    horizons = (1, 4, 12)
    max_h = max(horizons)
    cost = args.round_trip_cost_bps / 10_000.0

    direction_events = []
    pa_events = []
    audits = []
    loaded = {}

    for d in dirs:
        symbol = d.name[: -len("_USDT:USDT")]
        data = test02.load_symbol_1h(root, d)
        if len(data) < args.min_history + max_h + 1:
            continue
        ts = data["ts"].astype(np.int64)
        close = data["c"].astype(np.float64)
        arrays = test02.build_direction_arrays(close, args.direction_threshold)
        gp = test02.gap_prefix(ts)
        loaded[symbol] = (data, arrays, gp)

        for i in range(args.min_history - 1, len(data) - max_h):
            if ((int(ts[i]) // HOUR_MS) % max(args.step_hours, 1)) != 0:
                continue
            if not test02.contiguous(gp, i - args.min_history + 1, i):
                continue
            if not test02.contiguous(gp, i, i + max_h):
                continue
            dval = int(arrays["direction"][i])
            if dval == 0:
                continue
            direction = "LONG" if dval > 0 else "SHORT"
            base = float(close[i])
            fwds = [float(close[i+h]) for h in horizons]
            if not (base > 0.0 and math.isfinite(base) and all(x > 0.0 and math.isfinite(x) for x in fwds)):
                continue

            row = {
                "symbol": symbol,
                "ts": int(ts[i]),
                "direction": direction,
                "direction_score": float(arrays["score"][i]),
            }
            for h, px in zip(horizons, fwds):
                r = px / base - 1.0
                row[f"signed_{h}h"] = dval * r
            direction_events.append(dict(row))

            pa = pa_decision(data, i, direction, args.pa_threshold, args.min_pa_votes)
            if not pa.passed:
                continue
            row.update({
                "pa_score": pa.score,
                "pa_votes": pa.aligned_votes,
                "pa": {k: safe_num(v) if isinstance(v, float) else v for k, v in asdict(pa).items()},
            })
            pa_events.append(row)

    for raw in args.audit:
        symbol, expected, event_ms = parse_audit(raw)
        item = {"symbol": symbol, "expected": expected, "event_ms": event_ms}
        if symbol not in loaded:
            item["status"] = "MISSING_CACHE"
            audits.append(item)
            continue
        data, arrays, gp = loaded[symbol]
        ts = data["ts"].astype(np.int64)
        idxs = np.where(ts <= event_ms - HOUR_MS)[0]
        if not len(idxs):
            item["status"] = "NO_CLOSED_CANDLE"
            audits.append(item)
            continue
        i = int(idxs[-1])
        if i < args.min_history - 1 or not test02.contiguous(gp, i - args.min_history + 1, i):
            item["status"] = "INSUFFICIENT_OR_GAPPED_HISTORY"
            audits.append(item)
            continue
        ddec = test02.decision_at(arrays, i)
        item["direction_gate"] = {
            "direction": ddec.direction,
            "score": safe_num(ddec.score),
            "allows_expected": ddec.direction == expected,
        }
        if ddec.direction != expected:
            item["price_action"] = {"evaluated": False, "reason": "direction_veto"}
            item["final_allow"] = False
        else:
            pdec = pa_decision(data, i, expected, args.pa_threshold, args.min_pa_votes)
            item["price_action"] = {
                "evaluated": True,
                **{k: safe_num(v) if isinstance(v, float) else v for k, v in asdict(pdec).items()},
            }
            item["final_allow"] = bool(pdec.passed)
        item["status"] = "OK"
        audits.append(item)

    report = {
        "test": "GRID V2 TEST #03 Direction veto + Price Action shadow",
        "mode": "READ_ONLY_NO_ORDERS",
        "parameters": {
            "direction_threshold": args.direction_threshold,
            "pa_threshold": args.pa_threshold,
            "min_pa_votes": args.min_pa_votes,
            "min_history_hours": args.min_history,
            "sample_step_hours": args.step_hours,
            "round_trip_cost_bps": args.round_trip_cost_bps,
            "pa_weights": {
                "structure": 0.30,
                "breakout_retest": 0.20,
                "liquidity_sweep": 0.20,
                "rejection": 0.15,
                "compression_expansion": 0.15,
            },
        },
        "coverage": {
            "cache_symbol_dirs": len(dirs),
            "direction_events": len(direction_events),
            "pa_pass_events": len(pa_events),
            "pa_pass_rate": (len(pa_events) / len(direction_events)) if direction_events else 0.0,
            "pa_long_events": sum(1 for s in pa_events if s["direction"] == "LONG"),
            "pa_short_events": sum(1 for s in pa_events if s["direction"] == "SHORT"),
        },
        "direction_only_performance": {
            "overall": summarize(direction_events, horizons, cost),
            "long": summarize([s for s in direction_events if s["direction"] == "LONG"], horizons, cost),
            "short": summarize([s for s in direction_events if s["direction"] == "SHORT"], horizons, cost),
        },
        "price_action_gated_performance": {
            "overall": summarize(pa_events, horizons, cost),
            "long": summarize([s for s in pa_events if s["direction"] == "LONG"], horizons, cost),
            "short": summarize([s for s in pa_events if s["direction"] == "SHORT"], horizons, cost),
        },
        "audit": audits,
    }

    print("=== TEST03 SUMMARY ===")
    print(json.dumps(report["coverage"], sort_keys=True))
    print("=== DIRECTION ONLY ===")
    for group, stats in report["direction_only_performance"].items():
        print(f"-- {group.upper()} --")
        for h, row in stats.items():
            print(h, json.dumps(row, sort_keys=True))
    print("=== PRICE ACTION GATED ===")
    for group, stats in report["price_action_gated_performance"].items():
        print(f"-- {group.upper()} --")
        for h, row in stats.items():
            print(h, json.dumps(row, sort_keys=True))
    print("=== TEST01 ENTRY AUDIT ===")
    for item in audits:
        print(json.dumps(item, sort_keys=True))

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"REPORT {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
