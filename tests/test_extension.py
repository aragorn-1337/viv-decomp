"""Tests for the Vivisect extension module (viv_extension.py).

Uses fake vw/vwgui objects implementing the Vivisect extension API surface.
Qt GUI parts are exercised only if a binding is present (headless otherwise).
"""
import sys, os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
import viv_extension as ext


class FakeVw:
    def __init__(self, funcs):
        self._funcs = funcs  # {fva: name}
        self.printed = []

    def getName(self, va):
        return self._funcs.get(va) or f"func_{va:x}"

    def getFunction(self, va):
        return va if va in self._funcs else None

    def getFunctions(self):
        return sorted(self._funcs.keys())

    def vprint(self, s):
        self.printed.append(s)


class TestFuncAt:
    def test_exact_entry(self):
        vw = FakeVw({0x1000: "main"})
        assert ext._func_at(vw, 0x1000) == 0x1000

    def test_nonexact_fallback(self):
        vw = FakeVw({0x1000: "main", 0x2000: "helper"})
        # address inside/near 0x2000 -> nearest entry <= it
        assert ext._func_at(vw, 0x20F0) == 0x2000

    def test_no_function_none(self):
        vw = FakeVw({})
        assert ext._func_at(vw, 0x1000) is None


class TestDecompileText:
    def test_returns_text(self):
        class FakeDecomp:
            def decompile_address(self, fva):
                return type("O", (), {"text": "int main() {}"})()

        assert ext._decompile_text(FakeDecomp(), 0x1000) == "int main() {}"

    def test_error_fallback(self):
        class FakeDecomp:
            def decompile_address(self, fva):
                return type("O", (), {"text": ""})()

        assert ext._decompile_text(FakeDecomp(), 0x1000) == "// error"

    def test_none_output(self):
        class FakeDecomp:
            def decompile_address(self, fva):
                return None
        assert ext._decompile_text(FakeDecomp(), 0x1000) == "// error"


class TestVivExtension:
    @pytest.fixture
    def qapp(self):
        try:
            from PyQt6.QtWidgets import QApplication
        except ImportError:
            return None
        return QApplication.instance() or QApplication([])

    def _make_gui(self):
        class FakeGui:
            def __init__(self):
                self.menu_fields = []
                self.docks = {}
                self.registered = []
            def getVa(self):
                return 0x1000
            def vqAddMenuField(self, path, cb):
                self.menu_fields.append((path, cb))
            def vqDockWidget(self, widget, floating=False):
                self.docks[id(widget)] = widget
                return widget
            def vqGetDockWidgetsByName(self, name):
                return list(self.docks.items())
        return FakeGui()

    def _setup(self, vw):
        from viv_decomp.decompiler import VivisectDecompiler
        from viv_decomp.workspace_builder import WorkspaceGraphBuilder
        builder = WorkspaceGraphBuilder("<ws>")
        vw.getFunctionGraph = lambda fva: _fake_graph(fva)
        vw._filename = "<ws>"
        vw._vvd_decomp = VivisectDecompiler.from_workspace(vw)
        return vw

    def test_registers_menu_and_decomp(self, qapp):
        vw = FakeVw({0x1000: "main"})
        gui = self._make_gui()
        self._setup(vw)
        ext.vivExtension(vw, gui)
        assert any("Decompile" in p for p, _cb in gui.menu_fields)
        assert len(gui.docks) >= 1

    def test_vprint_on_load(self, qapp):
        vw = FakeVw({0x1000: "main"})
        gui = self._make_gui()
        self._setup(vw)
        ext.vivExtension(vw, gui)
        assert any("loaded" in p for p in vw.printed)

    def test_headless_no_qapp(self):
        # Ensure extension logic (menu registration) works when the dock
        # creation returns None (headless: no Qt GUI available).
        vw = FakeVw({0x1000: "main"})
        gui = self._make_gui()
        self._setup(vw)
        saved = ext._make_dock
        ext._make_dock = lambda vw, vwgui: None
        try:
            ext.vivExtension(vw, gui)
            assert any("Decompile" in p for p, _cb in gui.menu_fields)
        finally:
            ext._make_dock = saved


def _fake_graph(fva):
    from dec_engine.dec_impl.ir.block import BasicBlock, BlockGraph
    entry = BasicBlock(addr=fva, is_entry=True)
    return BlockGraph(entry_block=entry, blocks={fva: entry})
