#!/usr/bin/env python3
"""GRID V2 TEST #02: shadow Direction / Quality Gate evaluation.

Read-only evaluator. It never connects to an exchange and never creates orders.
It reads Passivbot's local 1h OHLCV cache, produces causal LONG/SHORT/NEUTRAL
signals, and measures forward directional returns.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

HOUR_MS = 3_600_000
REQUIRED_FIELDS = ("ts", "o", "h", "l", "c", "bv")


@dataclass(frozen=True)
class DirectionDecision:
    direction: str
    score: float
    confidence: float
    ema_spread: float
    ema_slope: float
    momentum: float
    positive_votes: int
    negative_votes: int


def ema(values: np.ndarray, span: int) -> np.ndarray:
    out = np.empty(len(values), dtype=np.float64)
    if len(values) == 0:
        return out
    alpha = 2.0 / (float(span) + 1.0)
    out[0] = float(values[0])
    for i in range(1, len(values)):
        out[i] = alpha * float(values[i]) + (1.0 - alpha) * out[i - 1]
    return out


def rolling_logret_vol(close: np.ndarray, window: int = 24) -> np.ndarray:
    close = close.astype(np.float64, copy=False)
    out = np.full(len(close), np.nan, dtype=np.float64)
    if len(close) <= window:
        return out
    lr = np.full(len(close), np.nan, dtype=np.float64)
    valid = (close[1:] > 0.0) & (close[:-1] > 0.0)
    lr[1:][valid] = np.log(close[1:][valid] / close[:-1][valid])
    for i in range(window, len(close)):
        w = lr[i - window + 1 : i + 1]
        if np.isfinite(w).all():
            out[i] = max(float(np.std(w, ddof=0)), 1e-8)
    return out


def build_direction_arrays(
    close: np.ndarray,
    threshold: float = 0.18,
) -> dict[str, np.ndarray]:
    close = close.astype(np.float64, copy=False)
    n = len(close)
    fast = ema(close, 12)
    slow = ema(close, 36)
    vol = rolling_logret_vol(close, 24)

    spread = np.full(n, np.nan, dtype=np.float64)
    slope = np.full(n, np.nan, dtype=np.float64)
    momentum = np.full(n, np.nan, dtype=np.float64)

    ok = (close > 0.0) & (fast > 0.0) & (slow > 0.0) & np.isfinite(vol)
    spread[ok] = (fast[ok] / slow[ok] - 1.0) / (vol[ok] * math.sqrt(12.0))

    for i in range(6, n):
        if not ok[i] or slow[i - 6] <= 0.0 or close[i - 6] <= 0.0:
            continue
        slope[i] = math.log(slow[i] / slow[i - 6]) / (vol[i] * math.sqrt(6.0))
        momentum[i] = math.log(close[i] / close[i - 6]) / (vol[i] * math.sqrt(6.0))

    def squash(x: np.ndarray) -> np.ndarray:
        return np.clip(x, -3.0, 3.0) / 3.0

    z_spread = squash(spread)
    z_slope = squash(slope)
    z_momentum = squash(momentum)
    score = 0.45 * z_spread + 0.30 * z_slope + 0.25 * z_momentum

    vote_floor = 0.03
    pos_votes = (
        (z_spread > vote_floor).astype(np.int8)
        + (z_slope > vote_floor).astype(np.int8)
        + (z_momentum > vote_floor).astype(np.int8)
    )
    neg_votes = (
        (z_spread < -vote_floor).astype(np.int8)
        + (z_slope < -vote_floor).astype(np.int8)
        + (z_momentum < -vote_floor).astype(np.int8)
    )

    direction = np.zeros(n, dtype=np.int8)
    finite = np.isfinite(score)
    direction[finite & (score >= threshold) & (pos_votes >= 2)] = 1
    direction[finite & (score <= -threshold) & (neg_votes >= 2)] = -1
    confidence = np.clip(np.abs(score) / max(threshold * 2.0, 1e-9), 0.0, 1.0)

    return {
        "fast": fast,
        "slow": slow,
        "vol": vol,
        "ema_spread": z_spread,
        "ema_slope": z_slope,
        "momentum": z_momentum,
        "score": score,
        "positive_votes": pos_votes,
        "negative_votes": neg_votes,
        "direction": direction,
        "confidence": confidence,
    }


def decision_at(arrays: dict[str, np.ndarray], i: int) -> DirectionDecision:
    d = int(arrays["direction"][i])
    label = "LONG" if d > 0 else "SHORT" if d < 0 else "NEUTRAL"
    return DirectionDecision(
        direction=label,
        score=float(arrays["score"][i]) if np.isfinite(arrays["score"][i]) else float("nan"),
        confidence=float(arrays["confidence"][i]) if np.isfinite(arrays["confidence"][i]) else 0.0,
        ema_spread=float(arrays["ema_spread"][i]) if np.isfinite(arrays["ema_spread"][i]) else float("nan"),
        ema_slope=float(arrays["ema_slope"][i]) if np.isfinite(arrays["ema_slope"][i]) else float("nan"),
        momentum=float(arrays["momentum"][i]) if np.isfinite(arrays["momentum"][i]) else float("nan"),
        positive_votes=int(arrays["positive_votes"][i]),
        negative_votes=int(arrays["negative_votes"][i]),
    )


def load_symbol_1h(root: Path, symbol_dir: Path) -> np.ndarray:
    parts = []
    for path in sorted(symbol_dir.glob("*.npy")):
        a = np.load(path, allow_pickle=False)
        if a.dtype.names is None or any(name not in a.dtype.names for name in REQUIRED_FIELDS):
            raise ValueError(f"unexpected candle dtype in {path}: {a.dtype}")
        if len(a):
            parts.append(a)
    if not parts:
        return np.empty(0, dtype=[("ts", "<i8"), ("o", "<f4"), ("h", "<f4"), ("l", "<f4"), ("c", "<f4"), ("bv", "<f4")])
    data = np.concatenate(parts)
    order = np.argsort(data["ts"], kind="stable")
    data = data[order]
    _, reverse_idx = np.unique(data["ts"][::-1], return_index=True)
    keep = np.sort(len(data) - 1 - reverse_idx)
    return data[keep]


def gap_prefix(ts: np.ndarray) -> np.ndarray:
    if len(ts) <= 1:
        return np.zeros(len(ts), dtype=np.int64)
    bad = (np.diff(ts.astype(np.int64)) != HOUR_MS).astype(np.int64)
    return np.concatenate((np.array([0], dtype=np.int64), np.cumsum(bad)))


def contiguous(prefix: np.ndarray, left: int, right: int) -> bool:
    if left < 0 or right >= len(prefix) or right < left:
        return False
    return int(prefix[right] - prefix[left]) == 0


def parse_audit(value: str) -> tuple[str, str, int]:
    symbol, expected, iso = value.split(",", 2)
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return symbol.upper(), expected.lower(), int(dt.timestamp() * 1000)


def safe_num(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def summarize(samples: list[dict], horizons: Iterable[int], round_trip_cost: float) -> dict:
    out = {}
    for h in horizons:
        vals = np.asarray([s[f"signed_{h}h"] for s in samples], dtype=np.float64)
        vals = vals[np.isfinite(vals)]
        if len(vals) == 0:
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
            "extreme_abs_gt_20pct_rate": float(np.mean(np.abs(vals) > 0.20)),
            "p01_gross_signed_return": q01,
            "p10_gross_signed_return": float(np.quantile(vals, 0.10)),
            "p90_gross_signed_return": float(np.quantile(vals, 0.90)),
            "p99_gross_signed_return": q99,
        }
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="caches/ohlcv/binance/1h")
    p.add_argument("--threshold", type=float, default=0.18)
    p.add_argument("--min-history", type=int, default=48)
    p.add_argument("--step-hours", type=int, default=4)
    p.add_argument("--round-trip-cost-bps", type=float, default=4.0)
    p.add_argument("--max-symbols", type=int, default=0)
    p.add_argument("--audit", action="append", default=[])
    p.add_argument("--json-out")
    args = p.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        raise SystemExit(f"missing cache root: {root}")

    horizons = (1, 4, 12)
    max_h = max(horizons)
    cost = args.round_trip_cost_bps / 10_000.0

    dirs = sorted([d for d in root.iterdir() if d.is_dir() and d.name.endswith("_USDT:USDT")])
    if args.max_symbols > 0:
        dirs = dirs[: args.max_symbols]

    samples: list[dict] = []
    symbol_stats = {}
    latest_rows = []
    loaded = {}

    for d in dirs:
        symbol = d.name[: -len("_USDT:USDT")]
        data = load_symbol_1h(root, d)
        if len(data) < args.min_history + max_h + 1:
            continue
        ts = data["ts"].astype(np.int64)
        close = data["c"].astype(np.float64)
        arrays = build_direction_arrays(close, args.threshold)
        gp = gap_prefix(ts)
        loaded[symbol] = (data, arrays, gp)

        sym_events = 0
        sym_long = 0
        sym_short = 0
        for i in range(args.min_history - 1, len(data) - max_h):
            if ((int(ts[i]) // HOUR_MS) % max(args.step_hours, 1)) != 0:
                continue
            if not contiguous(gp, i - args.min_history + 1, i):
                continue
            if not contiguous(gp, i, i + max_h):
                continue
            direction = int(arrays["direction"][i])
            if direction == 0:
                continue
            base = float(close[i])
            if not (base > 0.0 and math.isfinite(base)):
                continue
            forward_prices = [float(close[i + h]) for h in horizons]
            if not all(price > 0.0 and math.isfinite(price) for price in forward_prices):
                continue
            row = {
                "symbol": symbol,
                "ts": int(ts[i]),
                "direction": "LONG" if direction > 0 else "SHORT",
                "score": float(arrays["score"][i]),
            }
            for h, future_price in zip(horizons, forward_prices):
                r = float(future_price / base - 1.0)
                row[f"signed_{h}h"] = direction * r
            samples.append(row)
            sym_events += 1
            sym_long += int(direction > 0)
            sym_short += int(direction < 0)

        if sym_events:
            symbol_stats[symbol] = {"events": sym_events, "long": sym_long, "short": sym_short}

        i = len(data) - 1
        dec = decision_at(arrays, i)
        latest_rows.append({
            "symbol": symbol,
            "ts": int(ts[i]),
            **{k: safe_num(v) if isinstance(v, float) else v for k, v in asdict(dec).items()},
        })

    longs = sum(1 for s in samples if s["direction"] == "LONG")
    shorts = sum(1 for s in samples if s["direction"] == "SHORT")

    audits = []
    for raw in args.audit:
        symbol, expected, event_ms = parse_audit(raw)
        item = {"symbol": symbol, "expected": expected.upper(), "event_ms": event_ms}
        if symbol not in loaded:
            item["status"] = "MISSING_CACHE"
            audits.append(item)
            continue
        data, arrays, gp = loaded[symbol]
        ts = data["ts"].astype(np.int64)
        cutoff = event_ms - HOUR_MS
        indices = np.where(ts <= cutoff)[0]
        if len(indices) == 0:
            item["status"] = "NO_CLOSED_CANDLE"
            audits.append(item)
            continue
        i = int(indices[-1])
        if i < args.min_history - 1 or not contiguous(gp, i - args.min_history + 1, i):
            item["status"] = "INSUFFICIENT_OR_GAPPED_HISTORY"
            audits.append(item)
            continue
        dec = decision_at(arrays, i)
        item.update({
            "status": "OK",
            "signal_candle_ts": int(ts[i]),
            **{k: safe_num(v) if isinstance(v, float) else v for k, v in asdict(dec).items()},
            "would_allow_expected_direction": dec.direction == expected.upper(),
            "would_veto": dec.direction != expected.upper(),
        })
        audits.append(item)

    latest_long = sorted(
        [r for r in latest_rows if r["direction"] == "LONG" and r["score"] is not None],
        key=lambda r: r["score"],
        reverse=True,
    )[:10]
    latest_short = sorted(
        [r for r in latest_rows if r["direction"] == "SHORT" and r["score"] is not None],
        key=lambda r: r["score"],
    )[:10]

    report = {
        "test": "GRID V2 TEST #02 shadow Direction/Quality Gate",
        "mode": "READ_ONLY_NO_ORDERS",
        "root": str(root),
        "parameters": {
            "threshold": args.threshold,
            "min_history_hours": args.min_history,
            "sample_step_hours": args.step_hours,
            "round_trip_cost_bps": args.round_trip_cost_bps,
            "weights": {"ema_spread": 0.45, "ema_slope": 0.30, "momentum_6h": 0.25},
            "quality_gate": "score threshold + >=2/3 directional votes + contiguous history",
        },
        "coverage": {
            "cache_symbol_dirs": len(dirs),
            "eligible_symbols": len(loaded),
            "symbols_with_events": len(symbol_stats),
            "events": len(samples),
            "long_events": longs,
            "short_events": shorts,
        },
        "performance": {
            "overall": summarize(samples, horizons, cost),
            "long": summarize([s for s in samples if s["direction"] == "LONG"], horizons, cost),
            "short": summarize([s for s in samples if s["direction"] == "SHORT"], horizons, cost),
        },
        "audit": audits,
        "latest_top_long": latest_long,
        "latest_top_short": latest_short,
    }

    print("=== TEST02 SUMMARY ===")
    print(json.dumps(report["coverage"], sort_keys=True))
    for group, group_stats in report["performance"].items():
        print(f"-- {group.upper()} --")
        for h, stats in group_stats.items():
            print(h, json.dumps(stats, sort_keys=True))
    print("=== TEST01 ENTRY AUDIT ===")
    for item in audits:
        print(json.dumps(item, sort_keys=True))
    print("=== LATEST TOP LONG ===")
    for item in latest_long[:5]:
        print(json.dumps(item, sort_keys=True))
    print("=== LATEST TOP SHORT ===")
    for item in latest_short[:5]:
        print(json.dumps(item, sort_keys=True))

    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"REPORT {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
