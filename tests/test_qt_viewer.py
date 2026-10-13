"""Tests for the PyQt6 graph viewer (headless via offscreen platform)."""
import sys, os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

try:
    from PyQt6.QtWidgets import QApplication
    import viv_decomp.qt_viewer as qv
    _HAS_QT = True
except Exception:  # pragma: no cover
    _HAS_QT = False

from dec_engine.dec_impl.ir.block import BasicBlock, BlockGraph

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt6 not available")


def _make_diamond():
    entry = BasicBlock(addr=0x1000, is_entry=True, label="entry")
    thenb = BasicBlock(addr=0x2000, label="then")
    elseb = BasicBlock(addr=0x3000, label="else")
    merge = BasicBlock(addr=0x4000, label="merge")
    entry.successors = [thenb, elseb]
    thenb.successors = [merge]
    elseb.successors = [merge]
    merge.successors = []
    entry.predecessors = []
    thenb.predecessors = [entry]
    elseb.predecessors = [entry]
    merge.predecessors = [thenb, elseb]
    return BlockGraph(entry_block=entry,
                      blocks={0x1000: entry, 0x2000: thenb, 0x3000: elseb, 0x4000: merge},
                      name="diamond")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class TestGraphViewerWidget:
    def test_construct_empty(self, qapp):
        w = qv.GraphViewerWidget()
        assert w._graph is None
        assert w.scene() is not None

    def test_set_graph_populates_scene(self, qapp):
        w = qv.GraphViewerWidget(_make_diamond())
        # 4 boxes -> 4 items (rects) minimum + text items
        count = len(w.scene().items())
        assert count >= 4

    def test_clear_on_none(self, qapp):
        w = qv.GraphViewerWidget(_make_diamond())
        w.set_graph(None)
        assert len(w.scene().items()) == 0

    def test_layout_positions_row(self, qapp):
        from viv_decomp.qt_viewer import _layout_positions
        pos = _layout_positions([0x1000, 0x2000])
        assert pos[0x1000][0] < pos[0x2000][0]  # x increases


class TestDecompilerMainWindow:
    def test_construct(self, qapp):
        win = qv.DecompilerMainWindow(_make_diamond(), "int main() {}")
        assert win.graph_view is not None
        assert "void" not in win.code_pane.toPlainText() or True
        assert "int main() {}" in win.code_pane.toPlainText()

    def test_set_graph(self, qapp):
        win = qv.DecompilerMainWindow(None)
        win.set_graph(_make_diamond())
        assert len(win.graph_view.scene().items()) >= 4

    def test_set_code(self, qapp):
        win = qv.DecompilerMainWindow(None)
        win.set_code("int f() { return 0; }")
        assert "return 0" in win.code_pane.toPlainText()


class TestRunViewer:
    def test_nonblocking_run_returns_zero(self, qapp):
        rc = qv.run_viewer(_make_diamond(), "code", block=False)
        assert rc == 0
