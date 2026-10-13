"""Integration tests for VivisectDecompiler.export_graph (raw builder, no binary)."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from viv_decomp.decompiler import VivisectDecompiler


@pytest.fixture
def decompiler():
    """A decompiler wired to the raw graph source (no binary needed)."""
    return VivisectDecompiler(binary_path="<raw>", graph_source="raw")


class TestExportGraphIntegration:
    def test_json_export(self, decompiler):
        out = decompiler.export_graph(0x1000, "json")
        data = json.loads(out)
        assert data["name"] == "func_1000"
        assert data["num_blocks"] >= 1

    def test_svg_export(self, decompiler):
        out = decompiler.export_graph(0x1000, "svg")
        assert out.startswith("<svg")
        assert "</svg>" in out

    def test_dot_export(self, decompiler):
        out = decompiler.export_graph(0x1000, "dot")
        assert out.startswith("digraph")

    def test_unknown_format_raises(self, decompiler):
        with pytest.raises(ValueError):
            decompiler.export_graph(0x1000, "bogus")

    def test_json_has_valid_edges(self, decompiler):
        out = decompiler.export_graph(0x1000, "json")
        data = json.loads(out)
        assert data["num_edges"] >= 1  # raw graph has entry->body edge
