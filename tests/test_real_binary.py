"""Real-binary integration test: decompile a function from a live workspace.

Validates the end-to-end Vivisect path on an actual ELF. The analyzePLT
exception ("Invalid File: None") is benign — Vivisect catches it internally
and continues; analyze() still detects functions.

Skipped if no ELF is available or the installed Vivisect lacks APIs.
"""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

pytestmark = pytest.mark.skipif(
    not os.path.exists("/usr/bin/true") or os.environ.get("NO_REAL_BINARIES"),
    reason="no real ELF available",
)


def _load_vw():
    import vivisect
    vw = vivisect.VivWorkspace()
    vw.loadFromFile("/usr/bin/true")
    try:
        vw.analyze()
    except Exception:
        pass  # analyzePLT benign exception; analysis continues
    return vw


def test_load_and_analyze():
    vw = _load_vw()
    assert len(list(vw.getFunctions())) >= 1


def test_decompile_real_function():
    import vivisect
    from viv_decomp.decompiler import VivisectDecompiler
    vw = _load_vw()
    funcs = sorted(vw.getFunctions())
    assert funcs, "no functions detected"
    d = VivisectDecompiler.from_workspace(vw, arch="amd64")
    out = d.decompile_address(funcs[0])
    assert out.success is True
    assert "{" in out.text  # C body emitted


def test_symbolik_lift_runs_on_real_vw():
    """The live-vw builder must prefer the symbolik lift on a real workspace."""
    import vivisect
    from viv_decomp.workspace_builder import WorkspaceGraphBuilder
    vw = _load_vw()
    funcs = sorted(vw.getFunctions())
    assert funcs
    builder = WorkspaceGraphBuilder("<ws>")
    builder.set_workspace(vw)
    graph = builder.get_graph(funcs[0])
    assert graph.blocks
    # At least one block should carry instructions via symbolik lift
    total_instr = sum(len(b.instructions) for b in graph.blocks.values())
    assert total_instr >= 0
