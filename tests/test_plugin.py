"""Tests for the plugin system (S8): registry, discovery, decompiler wiring."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from dec_engine.dec_impl.plugin import PluginRegistry, AnalysisPass, OutputFormatter
from dec_engine.dec_impl.plugin.registry import entry_point_pass, entry_point_formatter
from dec_engine.dec_impl.ir.block import BasicBlock, BlockGraph


def _make_graph():
    entry = BasicBlock(addr=0x1000, is_entry=True)
    bb = BasicBlock(addr=0x2000)
    entry.successors = [bb]
    bb.predecessors = [entry]
    bb.successors = [entry]  # loop
    return BlockGraph(entry_block=entry,
                      blocks={0x1000: entry, 0x2000: bb}, name="f")


class _CountPass(AnalysisPass):
    name = "count"
    def analyze(self, graph):
        graph.metadata["count"] = len(graph.blocks)
        return graph


class _UppercaseFormatter(OutputFormatter):
    name = "upper"
    def format(self, output):
        return output.text.upper()


class TestAnalysisPassProtocol:
    def test_is_plugin(self):
        p = _CountPass()
        assert isinstance(p, AnalysisPass)
        assert p.name == "count"

    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            AnalysisPass()

    def test_analyze_returns_graph(self):
        p = _CountPass()
        g = _make_graph()
        out = p.analyze(g)
        assert out.metadata["count"] == 2


class TestOutputFormatterProtocol:
    def test_is_plugin(self):
        f = _UppercaseFormatter()
        assert isinstance(f, OutputFormatter)
        assert f.name == "upper"

    def test_abstract(self):
        with pytest.raises(TypeError):
            OutputFormatter()


class TestPluginRegistry:
    def test_register_pass(self):
        reg = PluginRegistry()
        reg.register_pass(_CountPass())
        assert reg.has_pass("count")
        assert "count" in reg.pass_names()

    def test_register_formatter(self):
        reg = PluginRegistry()
        reg.register_formatter(_UppercaseFormatter())
        assert reg.has_formatter("upper")
        assert "upper" in reg.formatter_names()

    def test_register_non_pass_raises(self):
        reg = PluginRegistry()
        with pytest.raises(TypeError):
            reg.register_pass("not a pass")

    def test_get_pass(self):
        reg = PluginRegistry()
        reg.register_pass(_CountPass())
        assert reg.get_pass("count") is not None
        assert reg.get_pass("missing") is None

    def test_get_formatter(self):
        reg = PluginRegistry()
        reg.register_formatter(_UppercaseFormatter())
        assert reg.get_formatter("upper") is not None
        assert reg.get_formatter("nope") is None

    def test_run_passes_all(self):
        reg = PluginRegistry()
        reg.register_pass(_CountPass())
        g = _make_graph()
        out = reg.run_passes(g)
        assert out.metadata["count"] == 2

    def test_run_passes_selected(self):
        reg = PluginRegistry()
        reg.register_pass(_CountPass())
        g = _make_graph()
        out = reg.run_passes(g, ["count"])
        assert out.metadata["count"] == 2

    def test_run_passes_skips_unknown(self):
        reg = PluginRegistry()
        g = _make_graph()
        out = reg.run_passes(g, ["nonexistent"])
        assert out is g  # unchanged, just warning

    def test_format_output_by_name(self):
        reg = PluginRegistry()
        reg.register_formatter(_UppercaseFormatter())
        assert reg.format_output(type("O", (), {"text": "abc"})(), "upper") == "ABC"

    def test_format_output_no_formatters_raises(self):
        reg = PluginRegistry()
        with pytest.raises(ValueError):
            reg.format_output(type("O", (), {"text": "abc"})())

    def test_format_output_unknown_raises(self):
        reg = PluginRegistry()
        reg.register_formatter(_UppercaseFormatter())
        with pytest.raises(KeyError):
            reg.format_output(type("O", (), {"text": "abc"})(), "nope")


class TestDiscovery:
    def test_discover_recursive(self):
        reg = PluginRegistry()
        demo_dir = os.path.join(os.path.dirname(__file__), "plugins_demo")
        reg.discover_from([demo_dir], recursive=True)
        assert reg.has_pass("graph_stats")

    def test_discover_flat(self):
        reg = PluginRegistry()
        demo_dir = os.path.join(os.path.dirname(__file__), "plugins_demo")
        reg.discover_from([demo_dir], recursive=False)
        assert reg.has_pass("graph_stats")

    def test_discover_single_file(self):
        reg = PluginRegistry()
        demo = os.path.join(os.path.dirname(__file__), "plugins_demo", "graph_stats.py")
        reg.discover_from([demo])
        assert reg.has_pass("graph_stats")

    def test_discover_runs_pass(self):
        reg = PluginRegistry()
        demo_dir = os.path.join(os.path.dirname(__file__), "plugins_demo")
        reg.discover_from([demo_dir])
        g = _make_graph()
        out = reg.run_passes(g, ["graph_stats"])
        assert out.metadata["plugin_stats"]["blocks"] == 2


class TestDecorators:
    def test_entry_point_pass_registers(self):
        reg = PluginRegistry()
        @entry_point_pass(registry=reg)
        class P(AnalysisPass):
            name = "decorated"
            def analyze(self, graph): return graph
        assert reg.has_pass("decorated")

    def test_entry_point_formatter_registers(self):
        reg = PluginRegistry()
        @entry_point_formatter(registry=reg)
        class F(OutputFormatter):
            name = "decor_fmt"
            def format(self, output): return output.text
        assert reg.has_formatter("decor_fmt")

    def test_can_use_bare_decorator(self):
        reg = PluginRegistry()
        @entry_point_pass(registry=reg)
        class Q(AnalysisPass):
            name = "q"
            def analyze(self, graph): return graph
        assert reg.has_pass("q")


class TestDecompilerIntegration:
    def _make_decompiler(self, reg=None, passes=None, formatter=None):
        from viv_decomp.decompiler import VivisectDecompiler
        return VivisectDecompiler(
            binary_path="<raw>", graph_source="raw",
            plugin_registry=reg, passes=passes, formatter=formatter,
        )

    def test_without_plugins(self):
        d = self._make_decompiler()
        out = d.decompile_address(0x1000)
        assert out.success

    def test_with_pass_annotates_metadata(self):
        reg = PluginRegistry()
        reg.register_pass(_CountPass())
        d = self._make_decompiler(reg=reg, passes=["count"])
        out = d.decompile_address(0x1000)
        assert out.success
        # metadata survives on decompiler.graph
        assert d.graph.metadata.get("count") == 2

    def test_with_formatter_override(self):
        reg = PluginRegistry()
        reg.register_formatter(_UppercaseFormatter())
        d = self._make_decompiler(reg=reg, formatter="upper")
        out = d.decompile_address(0x1000)
        assert out.text.isupper()
