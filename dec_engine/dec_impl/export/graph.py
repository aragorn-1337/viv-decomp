"""BlockGraph → JSON / SVG / DOT serialization.

Pure-Python generators (no graphviz / Qt) so exports run headless and in CI.
The SVG output is a deterministic layered graph suitable for static rendering.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from dec_engine.dec_impl.ir.block import BasicBlock, BlockGraph


def _instruction_text(block: BasicBlock) -> str:
    """Compact text summary of a block's instructions."""
    parts = []
    for instr in getattr(block, "instructions", [])[:6]:
        try:
            parts.append(str(instr))
        except Exception:
            parts.append("<expr>")
    return "\n".join(parts) if parts else "(no instructions)"


def export_json(graph: BlockGraph) -> str:
    """Serialize the graph to a structured JSON document."""
    nodes = []
    for addr, block in graph.blocks.items():
        nodes.append({
            "addr": hex(addr),
            "is_entry": getattr(block, "is_entry", False),
            "is_exit": getattr(block, "is_exit", False),
            "label": getattr(block, "label", ""),
            "instr_count": len(getattr(block, "instructions", [])),
            "text": _instruction_text(block),
        })
    succ_edges = []
    for addr, block in graph.blocks.items():
        for s in getattr(block, "successors", []):
            if hasattr(s, "addr"):
                succ_edges.append({"from": hex(addr), "to": hex(s.addr)})

    doc = {
        "name": graph.name or "",
        "entry": hex(graph.entry_block.addr) if graph.entry_block else None,
        "num_blocks": len(graph.blocks),
        "num_edges": len(succ_edges),
        "nodes": nodes,
        "edges": succ_edges,
    }
    return json.dumps(doc, indent=2)


_EPS = 12          # horizontal padding per box
_BOX_W = 160
_BOX_H = 60
_ROW_H = 120


def _layout(graph: BlockGraph):
    """Assign (col) coordinates; returns {addr: (x, y)} for box centers."""
    addrs = sorted(graph.blocks.keys())
    pos = {}
    for i, addr in enumerate(addrs):
        col = i
        pos[addr] = (col, 0)
    return pos


def export_svg(graph: BlockGraph) -> str:
    """Generate a deterministic SVG diagram of the CFG (headless, no deps)."""
    if not graph.blocks:
        return "<svg xmlns='http://www.w3.org/2000/svg' width='0' height='0'></svg>"

    pos = _layout(graph)
    width = len(graph.blocks) * (_BOX_W + _EPS) + _EPS
    height = _BOX_H + 40

    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' "
        f"height='{height}' viewBox='0 0 {width} {height}'>"
    )
    svg += "<defs><marker id='arr' markerWidth='10' markerHeight='10' " \
           "refX='9' refY='3' orient='auto'><path d='M0,0 L9,3 L0,6 Z' /></marker></defs>"

    # Edges
    for addr, block in graph.blocks.items():
        try:
            ex, ey = pos[addr]
            x1 = ex * (_BOX_W + _EPS) + _EPS
            y1 = _ROW_H // 2
        except KeyError:
            continue
        for s in getattr(block, "successors", []):
            if not hasattr(s, "addr"):
                continue
            try:
                sx, _sy = pos[s.addr]
                x2 = sx * (_BOX_W + _EPS) + _EPS
                y2 = _ROW_H // 2
            except KeyError:
                continue
            svg += (
                f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' "
                f"stroke='#444' stroke-width='1.5' marker-end='url(#arr)'/>"
            )

    # Nodes
    for addr, block in graph.blocks.items():
        try:
            cx, _cy = pos[addr]
            bx = cx * (_BOX_W + _EPS) + _EPS
            by = 20
        except KeyError:
            continue
        stroke = "#d33" if getattr(block, "is_entry", False) else "#333"
        fill = "#fff6e6" if getattr(block, "is_entry", False) else "#eef"
        label = getattr(block, "label", "") or f"bb_{addr:x}"
        esc = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        svg += (
            f"<g><rect x='{bx}' y='{by}' width='{_BOX_W}' height='{_BOX_H}' "
            f"rx='6' fill='{fill}' stroke='{stroke}' stroke-width='2'/>"
            f"<text x='{bx + _BOX_W // 2}' y='{by + _BOX_H // 2 + 5}' "
            f"text-anchor='middle' font-family='monospace' font-size='12'>"
            f"{esc}</text></g>"
        )

    svg += "</svg>"
    return svg


def graph_to_dot(graph: BlockGraph) -> str:
    """Generate Graphviz DOT source (text; rendering is external)."""
    lines = ["digraph CFG {"]
    lines.append('  graph [fontname="monospace"];')
    for addr, block in graph.blocks.items():
        shape = "doublecircle" if getattr(block, "is_entry", False) else "box"
        label = getattr(block, "label", "") or f"bb_{addr:x}"
        lines.append(f'  "bb_{addr:x}" [shape="{shape}", label="{label}"];')
    for addr, block in graph.blocks.items():
        for s in getattr(block, "successors", []):
            if hasattr(s, "addr"):
                lines.append(f'  "bb_{addr:x}" -> "bb_{s.addr:x}";')
    lines.append("}")
    return "\n".join(lines)
