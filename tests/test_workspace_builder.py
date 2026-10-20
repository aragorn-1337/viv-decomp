"""Tests for the live-workspace graph builder (Vivisect integration).

Uses a fake ``vw`` implementing the Vivisect function-graph API surface
(``getFunctionGraph`` / ``FuncBlockGraph``) so we can validate the builder
without loading a real binary (which hits the analyzePLT quirk).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from viv_decomp.workspace_builder import WorkspaceGraphBuilder


class FakeFuncBlockGraph:
    """Mimics vivisect.codegraph.FuncBlockGraph node/edge API."""

    # node_id -> (cbva, cbsize)
    _blocks = {}
    # (src_nid, dst_nid) codeflow edges
    _edges = []

    def __init__(self, blocks, edges):
        self._blocks = blocks
        self._edges = edges

    def getNodes(self):
        return [(nid, {"cbva": cb[0]}) for nid, cb in self._blocks.items()]

    def getCodeBlockBounds(self, nid):
        return self._blocks[nid]

    def getNode(self, va):
        for nid, (cbva, _s) in self._blocks.items():
            if cbva == va:
                return nid
        return None

    def getNodeByVa(self, va):
        return self.getNode(va)

    def getEdges(self):
        return [(s, d, None, {"codeflow": (self._blocks[s][0], self._blocks[d][0])})
                for s, d in self._edges]


class FakeWorkspace:
    """Mimics the Vivisect workspace API surface used by the builder."""

    def __init__(self, fva, blocks, edges):
        self._fva = fva
        self._blocks = blocks
        self._edges = edges

    def getFunctionGraph(self, fva):
        return FakeFuncBlockGraph(self._blocks, self._edges)

    def getFunctions(self):
        return [self._fva]

    def getName(self, va):
        return ""

    def vprint(self, s):
        pass

    def getFunctionMeta(self, funcva, key, default=None):
        meta = self.getFunctionMetaDict(funcva)
        return (meta or {}).get(key, default)

    def getFunctionMetaDict(self, funcva):
        return {"startea": self._fva}

    def getFunctionBlocks(self, funcva):
        return []

    def getCodeBlock(self, va):
        return (va, 0x10, self._fva)

    def getLocation(self, va):
        return (va, 0x1, 0, 1)  # (va, size, ltype, ltinfo)

    def getFunctionApi(self, funcva):
        return None


def _diamond_workspace():
    # 0x1000 -> {0x2000, 0x3000} -> 0x4000
    blocks = {
        1: (0x1000, 0x10),
        2: (0x2000, 0x10),
        3: (0x3000, 0x10),
        4: (0x4000, 0x10),
    }
    edges = [(1, 2), (1, 3), (2, 4), (3, 4)]
    return FakeWorkspace(0x1000, blocks, edges)


class TestWorkspaceGraphBuilder:
    def _make(self, vw):
        b = WorkspaceGraphBuilder("<workspace>")
        b.set_workspace(vw)
        return b

    def test_requires_workspace(self):
        b = WorkspaceGraphBuilder("<workspace>")
        with pytest.raises(RuntimeError):
            b.get_graph(0x1000)

    def test_builds_blocks(self):
        vw = _diamond_workspace()
        graph = self._make(vw).get_graph(0x1000)
        assert len(graph.blocks) == 4

    def test_entry_block(self):
        vw = _diamond_workspace()
        graph = self._make(vw).get_graph(0x1000)
        entry = graph.entry_block
        assert entry.addr == 0x1000
        assert entry.is_entry

    def test_successors_wired(self):
        vw = _diamond_workspace()
        graph = self._make(vw).get_graph(0x1000)
        entry = next(b for b in graph.blocks.values() if b.is_entry)
        assert len(entry.successors) == 2  # 0x2000, 0x3000

    def test_merge_predecessors(self):
        vw = _diamond_workspace()
        graph = self._make(vw).get_graph(0x1000)
        merge = graph.blocks[0x4000]
        assert len(merge.predecessors) == 2

    def test_blocks_carry_metadata(self):
        vw = _diamond_workspace()
        graph = self._make(vw).get_graph(0x1000)
        for bb in graph.blocks.values():
            assert bb.metadata.get("func_va") == 0x1000
            assert bb.metadata.get("block_size") == 0x10

    def test_empty_graph_fallback(self):
        fw = FakeWorkspace(0x1000, {}, [])
        graph = self._make(fw).get_graph(0x1000)
        assert len(graph.blocks) == 1
        assert graph.entry_block.addr == 0x1000

    def test_name(self):
        vw = _diamond_workspace()
        graph = self._make(vw).get_graph(0x1000, name="my_func")
        assert graph.name == "my_func"

    def test_fully_decompiles_via_from_workspace(self):
        """Live-workspace pipeline produces C output end-to-end."""
        from viv_decomp.decompiler import VivisectDecompiler
        vw = _diamond_workspace()
        d = VivisectDecompiler.from_workspace(vw)
        # Ensure it used the workspace builder (not the binary-loading one)
        from viv_decomp.workspace_builder import WorkspaceGraphBuilder
        assert isinstance(d.graph_builder, WorkspaceGraphBuilder)
        out = d.decompile_address(0x1000)
        assert out.success
        assert "{" in out.text  # C function body emitted

    def test_blocks_have_cfg_metadata(self):
        vw = _diamond_workspace()
        graph = self._make(vw).get_graph(0x1000)
        for addr, bb in graph.blocks.items():
            assert bb.metadata.get("func_va") == 0x1000
