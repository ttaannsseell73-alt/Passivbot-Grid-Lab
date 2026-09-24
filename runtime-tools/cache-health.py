#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

TF_MS = {"1m": 60_000, "1h": 3_600_000}


def inspect_index(path: Path, now_ms: int) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data.get("meta") if isinstance(data, dict) else {}
    meta = meta if isinstance(meta, dict) else {}
    shards = data.get("shards") if isinstance(data, dict) else {}
    shards = shards if isinstance(shards, dict) else {}

    tf = path.parent.parent.name
    symbol = path.parent.name
    period_ms = TF_MS.get(tf)
    last_final = int(meta.get("last_final_ts", 0) or 0)
    last_refresh = int(meta.get("last_refresh_ms", 0) or 0)
    rows = 0
    for item in shards.values():
        if isinstance(item, dict):
            try:
                rows += int(item.get("count", 0) or 0)
            except (TypeError, ValueError):
                pass

    latest_final = (
        (now_ms // period_ms) * period_ms - period_ms
        if period_ms
        else 0
    )
    lag_ms = max(0, latest_final - last_final) if last_final and latest_final else None
    fresh = bool(period_ms and last_final and lag_ms <= period_ms)
    return {
        "tf": tf,
        "symbol": symbol,
        "last_final_ts": last_final,
        "last_refresh_ms": last_refresh,
        "lag_ms": lag_ms,
        "fresh": fresh,
        "rows": rows,
        "shards": len(shards),
    }


def summarize(root: Path, now_ms: int) -> dict:
    rows = []
    errors = []
    for path in root.glob("*/*/index.json"):
        try:
            rows.append(inspect_index(path, now_ms))
        except Exception as exc:
            errors.append({"path": str(path), "error": type(exc).__name__})

    out = {"root": str(root), "now_ms": now_ms, "errors": errors, "timeframes": {}}
    for tf in sorted({row["tf"] for row in rows}):
        group = [row for row in rows if row["tf"] == tf]
        row_counts = [row["rows"] for row in group]
        fresh = [row for row in group if row["fresh"]]
        basis = [row for row in group if row["rows"] > 0 and row["last_final_ts"] > 0]
        stale = [row for row in group if row["rows"] > 0 and not row["fresh"]]
        empty = [row for row in group if row["rows"] <= 0 or row["last_final_ts"] <= 0]
        lags = [row["lag_ms"] for row in group if row["lag_ms"] is not None]
        out["timeframes"][tf] = {
            "indices": len(group),
            "basis": len(basis),
            "fresh": len(fresh),
            "stale": len(stale),
            "empty": len(empty),
            "fresh_pct": round(100.0 * len(fresh) / len(group), 2) if group else 0.0,
            "rows_min": min(row_counts) if row_counts else 0,
            "rows_median": int(statistics.median(row_counts)) if row_counts else 0,
            "rows_max": max(row_counts) if row_counts else 0,
            "lag_minutes_median": (
                round(statistics.median(lags) / 60_000.0, 2) if lags else None
            ),
            "fresh_sample": [row["symbol"] for row in fresh[:10]],
            "stale_sample": [row["symbol"] for row in stale[:10]],
            "empty_sample": [row["symbol"] for row in empty[:10]],
        }
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args()

    result = summarize(Path(args.root), int(time.time() * 1000))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )

    print("CACHE-HEALTH-PASS")
    for tf, stats in result["timeframes"].items():
        print(
            f"{tf} indices={stats['indices']} basis={stats['basis']} "
            f"fresh={stats['fresh']} ({stats['fresh_pct']:.2f}%) "
            f"stale={stats['stale']} empty={stats['empty']} "
            f"rows_med={stats['rows_median']} lag_med_min={stats['lag_minutes_median']}"
        )
        if stats["stale_sample"]:
            print(f"{tf} stale_sample={','.join(stats['stale_sample'])}")
        if stats["empty_sample"]:
            print(f"{tf} empty_sample={','.join(stats['empty_sample'])}")
    print(f"errors={len(result['errors'])}")


if __name__ == "__main__":
    main()
