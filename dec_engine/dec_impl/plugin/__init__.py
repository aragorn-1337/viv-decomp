"""Plugin system for decompiler passes and formatters.

Allows third-party extensions without modifying core code:
- ``AnalysisPass``: protocol for graph-analysis passes
- ``OutputFormatter``: protocol for output formatting
- ``PluginRegistry``: registration + lookup + discovery
"""
from dec_engine.dec_impl.plugin.registry import (
    AnalysisPass,
    OutputFormatter,
    Plugin,
    PluginRegistry,
    entry_point_pass,
    entry_point_formatter,
)

__all__ = [
    "AnalysisPass",
    "OutputFormatter",
    "Plugin",
    "PluginRegistry",
    "entry_point_pass",
    "entry_point_formatter",
]
