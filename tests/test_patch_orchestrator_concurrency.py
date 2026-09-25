import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1]
    / "runtime-tools"
    / "patch-orchestrator-concurrency.py"
)
spec = importlib.util.spec_from_file_location("orchestrator_patch", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _valid_fixture(body: str) -> str:
    return "async def fixture(self, ordered_symbols, load_symbol_bundle):\n    if True:\n" + body


def test_exact_pinned_shape_is_bounded_and_idempotent():
    source = _valid_fixture(mod.OLD)

    patched, report = mod.patch_text(source)

    assert report == {"already_patched": False, "matches": 1}
    assert mod.MARKER in patched
    assert mod.OLD not in patched
    assert 'context="orchestrator_ema"' in patched
    assert "for offset in range(0, len(ordered_symbols), ema_concurrency)" in patched
    assert "await asyncio.gather(*symbol_tasks, return_exceptions=True)" in patched

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
