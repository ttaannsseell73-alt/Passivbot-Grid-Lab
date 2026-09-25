import importlib.util
import sys
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).resolve().parents[1] / "runtime-tools" / "test03-price-action-shadow.py"
spec = importlib.util.spec_from_file_location("test03_price_action_shadow", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
assert spec.loader is not None
spec.loader.exec_module(mod)


def _arr(rows):
    dtype=[("ts","<i8"),("o","<f4"),("h","<f4"),("l","<f4"),("c","<f4"),("bv","<f4")]
    return np.array(rows,dtype=dtype)


def test_bullish_structure_and_rejection_can_pass():
    rows=[]
    px=100.0
    for i in range(60):
        o=px
        c=px*1.002
        h=max(o,c)*1.001
        l=min(o,c)*0.999
        rows.append((i*mod.HOUR_MS,o,h,l,c,1000+i))
        px=c
    # last bar with a stronger lower wick and higher close
    i=59
    prev=rows[-2][4]
    rows[-1]=(i*mod.HOUR_MS,prev,prev*1.012,prev*0.985,prev*1.008,5000.0)
    data=_arr(rows)
    d=mod.pa_decision(data,len(data)-1,"LONG",threshold=0.15,min_votes=1)
    assert d.score > 0.0
    assert d.aligned_votes >= 1


def test_bearish_sweep_is_negative_for_long_positive_for_short():
    rows=[]
    for i in range(40):
        base=100.0 + i*0.05
        rows.append((i*mod.HOUR_MS,base,base+0.5,base-0.5,base+0.1,1000.0))
    # sweep above prior high, close back below
    prior_hi=max(r[2] for r in rows[-10:])
    rows.append((40*mod.HOUR_MS,prior_hi-0.1,prior_hi+1.0,prior_hi-1.0,prior_hi-0.5,2000.0))
    data=_arr(rows)
    c_long=mod.pa_components(data,len(data)-1,"LONG")
    c_short=mod.pa_components(data,len(data)-1,"SHORT")
    assert c_long["liquidity_sweep"] < 0.0
    assert c_short["liquidity_sweep"] > 0.0


def test_flat_action_does_not_pass():
    rows=[(i*mod.HOUR_MS,100.0,100.1,99.9,100.0,1000.0) for i in range(60)]
    data=_arr(rows)
    d=mod.pa_decision(data,len(data)-1,"LONG")
    assert not d.passed
