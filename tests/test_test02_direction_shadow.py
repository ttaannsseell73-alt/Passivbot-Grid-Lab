import importlib.util
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).resolve().parents[1] / "runtime-tools" / "test02-direction-shadow.py"
spec = importlib.util.spec_from_file_location("test02_direction_shadow", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def _decision(close):
    arrays = mod.build_direction_arrays(np.asarray(close, dtype=np.float64), threshold=0.18)
    return mod.decision_at(arrays, len(close) - 1)


def test_uptrend_classifies_long():
    close = 100.0 * np.exp(np.linspace(0.0, 0.35, 120))
    d = _decision(close)
    assert d.direction == "LONG"
    assert d.score > 0.18
    assert d.positive_votes >= 2


def test_downtrend_classifies_short():
    close = 100.0 * np.exp(np.linspace(0.0, -0.35, 120))
    d = _decision(close)
    assert d.direction == "SHORT"
    assert d.score < -0.18
    assert d.negative_votes >= 2


def test_flat_series_is_neutral():
    close = np.full(120, 100.0, dtype=np.float64)
    d = _decision(close)
    assert d.direction == "NEUTRAL"


def test_gap_prefix_detects_non_hourly_gap():
    ts = np.asarray([0, mod.HOUR_MS, 2 * mod.HOUR_MS, 4 * mod.HOUR_MS], dtype=np.int64)
    prefix = mod.gap_prefix(ts)
    assert mod.contiguous(prefix, 0, 2)
    assert not mod.contiguous(prefix, 0, 3)
