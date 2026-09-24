import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "runtime-tools" / "patch-ranking-concurrency.py"
spec = importlib.util.spec_from_file_location("ranking_patch", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_exact_pinned_shapes_are_bounded_and_idempotent():
    source = (
        "header\n"
        + mod.SCALAR_OLD
        + "\nmiddle\n"
        + mod.SCALAR_OLD
        + "\nother\n"
        + mod.PAIR_OLD
        + "\nfooter\n"
    )

    patched, report = mod.patch_text(source)

    assert report == {"already_patched": False, "scalar": 2, "pair": 1}
    assert mod.MARKER in patched
    assert mod.SCALAR_OLD not in patched
    assert mod.PAIR_OLD not in patched
    assert "for offset in range(0, n, ranking_concurrency)" in patched

    again, report2 = mod.patch_text(patched)
    assert again == patched
    assert report2["already_patched"] is True


def test_refuses_unknown_source_shape():
    try:
        mod.patch_text("not passivbot")
    except RuntimeError as exc:
        assert "unexpected pinned source shape" in str(exc)
    else:
        raise AssertionError("expected fail-closed source-shape rejection")
