"""Graph builder that extracts a function CFG from a live Vivisect workspace.

This is the canonical Vivisect integration path used by the extension: instead
of re-loading the binary (which hits the ``analyzePLT`` quirk), it consumes the
already-loaded workspace ``vw`` via ``vw.getFunctionGraph(fva)`` — Vivisect's
own ``FuncBlockGraph`` of code-block nodes + codeflow edges.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WorkspaceGraphBuilder:
    """Build a BlockGraph from a live Vivisect workspace's function graph."""

    def __init__(self, binary_path: str, arch: Optional[str] = None,
                 workspace=None):
        self.binary_path = binary_path
        self.arch = arch
        self.vw = workspace

    def set_workspace(self, vw):
        self.vw = vw

    def load(self) -> None:
        """No-op: a live workspace is provided by the extension/GUI."""
        if self.vw is None:
            raise RuntimeError(
                "WorkspaceGraphBuilder requires a live workspace. Use "
                "VivisectDecompiler.from_workspace(vw) or set_workspace()."
            )

    def _code_blocks(self, fva):
        """Return {node_id: (cbva, cbsize)} for the function graph."""
        from viv_decomp.decompiler import VivisectDecompiler
        # Avoid circular import at module top; builder is used through the
        # decompiler pipeline which imports graph lazily.
        graph = self.vw.getFunctionGraph(fva)
        blocks = {}
        for nid, _ninfo in graph.getNodes():
            try:
                cbva, cbsize = graph.getCodeBlockBounds(nid)
                blocks[nid] = (cbva, cbsize)
            except Exception:
                continue
        return blocks, graph

    def get_graph(self, funcva: int, name: str = "") -> BlockGraph:
        """Build a BlockGraph from vw.getFunctionGraph(funcva)."""
        from dec_engine.dec_impl.ir.block import BasicBlock, BlockGraph

        if self.vw is None:
            self.load()
        vw = self.vw
        assert vw is not None

        try:
            fgraph = vw.getFunctionGraph(funcva)
        except Exception as exc:  # pragma: no cover
            logger.error("getFunctionGraph(%x) failed: %s", funcva, exc)
            raise

        nodes = list(fgraph.getNodes())
        if not nodes:
            # No graph — fall back to a single entry block
            entry = BasicBlock(addr=funcva, is_entry=True,
                               label=f"func_{funcva:x}")
            return BlockGraph(entry_block=entry,
                              blocks={funcva: entry},
                              name=name or f"func_{funcva:x}")

        # node_id -> (start, size)
        bounds = {}
        node_start = {}
        for nid, _info in nodes:
            try:
                cbva, cbsize = fgraph.getCodeBlockBounds(nid)
                bounds[nid] = (cbva, cbsize)
                node_start[nid] = cbva
            except Exception:
                continue
        if not bounds:
            bounds = {nid: (funcva, 1) for nid, _info in nodes}
            node_start = {nid: funcva for nid, _info in nodes}

        # entry node: the node containing funcva
        entry_nid = None
        try:
            entry_nid = fgraph.getNode(funcva) or fgraph.getNodeByVa(funcva)
        except Exception:
            entry_nid = None
        if entry_nid is None and bounds:
            entry_nid = min(bounds, key=lambda n: bounds[n][0])

        blocks = {}
        for nid, (start, size) in bounds.items():
            bb = BasicBlock(
                addr=start,
                label=f"bb_{start:x}",
                is_entry=(nid == entry_nid),
            )
            # store raw code-block metadata for downstream passes
            bb.metadata["func_va"] = funcva
            bb.metadata["block_size"] = size
            bb.metadata["cbva"] = start
            blocks[start] = bb

        # Wire CFG edges from codeflow edges.
        for edge in fgraph.getEdges():
            # edge is (nid1, nid2, eid, props); codeflow prop holds (va1, va2)
            props = edge[3] if len(edge) > 3 else {}
            codeflow = props.get("codeflow")
            if not codeflow:
                continue
            va1, va2 = codeflow
            if va1 in blocks and va2 in blocks:
                if blocks[va2] not in blocks[va1].successors:
                    blocks[va1].successors.append(blocks[va2])
                if blocks[va1] not in blocks[va2].predecessors:
                    blocks[va2].predecessors.append(blocks[va1])

        # If no edges wired (shouldn't happen), fall back to a single block
        if len(blocks) == 1:
            entry = next(iter(blocks.values()))
            return BlockGraph(entry_block=entry, blocks=blocks,
                              name=name or f"func_{funcva:x}")

        entry_block = blocks.get(funcva)
        if entry_block is None and node_start:
            # entry node address
            entry_va = node_start.get(entry_nid, funcva)
            entry_block = blocks.get(entry_va) or min(blocks.values(),
                                                      key=lambda b: b.addr)

        return BlockGraph(entry_block=entry_block, blocks=blocks,
                          name=name or f"func_{funcva:x}")
