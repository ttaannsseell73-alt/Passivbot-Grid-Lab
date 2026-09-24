import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "runtime-tools" / "cache-health.py"
spec = importlib.util.spec_from_file_location("cache_health", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def write_index(root, tf, symbol, *, last_final, last_refresh, count):
    path = root / tf / symbol / "index.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "meta": {
                    "last_final_ts": last_final,
                    "last_refresh_ms": last_refresh,
                },
                "shards": {"2026-09-24": {"count": count}},
            }
        ),
        encoding="utf-8",
    )


def test_cache_health_counts_fresh_stale_and_empty(tmp_path):
    now = 3_600_000 * 10 + 30_000
    latest_1m = (now // 60_000) * 60_000 - 60_000
    latest_1h = (now // 3_600_000) * 3_600_000 - 3_600_000

    write_index(tmp_path, "1m", "A", last_final=latest_1m, last_refresh=now, count=200)
    write_index(tmp_path, "1m", "B", last_final=latest_1m - 10 * 60_000, last_refresh=now, count=100)
    write_index(tmp_path, "1m", "C", last_final=0, last_refresh=0, count=0)
    write_index(tmp_path, "1h", "A", last_final=latest_1h, last_refresh=now, count=48)

    result = mod.summarize(tmp_path, now)

    one_m = result["timeframes"]["1m"]
    assert one_m["indices"] == 3
    assert one_m["fresh"] == 1
    assert one_m["stale"] == 1
    assert one_m["empty"] == 1
    assert one_m["rows_median"] == 100

    one_h = result["timeframes"]["1h"]
    assert one_h["fresh"] == 1
    assert one_h["basis"] == 1
