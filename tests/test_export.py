"""Tests for export module — JSON/SVG/DOT serialization of BlockGraph."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from dec_engine.dec_impl.ir.block import BasicBlock, BlockGraph
from dec_engine.dec_impl.export.graph import export_json, export_svg, graph_to_dot


def _make_diamond():
    entry = BasicBlock(addr=0x1000, is_entry=True)
    thenb = BasicBlock(addr=0x2000)
    elseb = BasicBlock(addr=0x3000)
    merge = BasicBlock(addr=0x4000)
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


def _make_single():
    entry = BasicBlock(addr=0x1000, is_entry=True)
    entry.label = "entry"
    return BlockGraph(entry_block=entry, blocks={0x1000: entry}, name="single")


class TestExportJson:
    def test_empty_graph(self):
        g = BlockGraph(entry_block=None, blocks={})
        data = json.loads(export_json(g))
        assert data["num_blocks"] == 0
        assert data["entry"] is None

    def test_diamond_counts(self):
        data = json.loads(export_json(_make_diamond()))
        assert data["num_blocks"] == 4
        assert data["num_edges"] == 4  # entry->then, entry->else, then->merge, else->merge
        assert data["name"] == "diamond"

    def test_entry_marked(self):
        data = json.loads(export_json(_make_diamond()))
        entry_node = next(n for n in data["nodes"] if n["is_entry"])
        assert entry_node["addr"] == "0x1000"

    def test_edges_direction(self):
        data = json.loads(export_json(_make_diamond()))
        edge_from = {e["from"] for e in data["edges"]}
        assert "0x1000" in edge_from

    def test_single_node(self):
        data = json.loads(export_json(_make_single()))
        assert data["num_blocks"] == 1
        assert data["entry"] == "0x1000"


class TestExportSvg:
    def test_empty_graph(self):
        g = BlockGraph(entry_block=None, blocks={})
        svg = export_svg(g)
        assert len(svg) == 0 or "<svg" in svg

    def test_diamond_has_nodes(self):
        svg = export_svg(_make_diamond())
        assert svg.count("<rect") == 4  # one box per block

    def test_diamond_has_edges(self):
        svg = export_svg(_make_diamond())
        assert svg.count("<line") == 4

    def test_entry_highlight(self):
        svg = export_svg(_make_diamond())
        assert "#d33" in svg  # entry stroke color

    def test_svg_valid_root(self):
        svg = export_svg(_make_diamond())
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")


class TestGraphToDot:
    def test_empty(self):
        g = BlockGraph(entry_block=None, blocks={})
        dot = graph_to_dot(g)
        assert dot.startswith("digraph")

    def test_diamond_nodes_edges(self):
        dot = graph_to_dot(_make_diamond())
        assert dot.count('->') == 4
        assert '"bb_1000" [' in dot  # node declaration present

    def test_entry_shape(self):
        dot = graph_to_dot(_make_diamond())
        assert 'doublecircle' in dot

    def test_roundtrip_edges(self):
        dot = graph_to_dot(_make_diamond())
        assert '"bb_1000" -> "bb_2000"' in dot
        assert '"bb_2000" -> "bb_4000"' in dot
