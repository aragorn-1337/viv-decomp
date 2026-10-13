"""Graph export: JSON and SVG serialization of decompiler CFGs.

Headless, dependency-free export of a ``BlockGraph`` so frontends/CI can
consume or render the CFG without a Qt stack:
- ``export_json``: structured graph JSON
- ``export_svg``: deterministic SVG diagram (no graphviz needed)

Part of the S6 frontend scope's export deliverables, kept Qt-free for CI.
"""
from dec_engine.dec_impl.export.graph import (
    export_json,
    export_svg,
    graph_to_dot,
)

__all__ = ["export_json", "export_svg", "graph_to_dot"]
