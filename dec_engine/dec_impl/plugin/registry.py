"""Plugin registry: register, discover, and run decompiler extensions.

Two extension kinds are supported:

1. **Analysis passes** — transform or annotate a ``BlockGraph`` (e.g. a
   stack-frame or call-graph pass). Protocol: ``name`` and ``analyze(graph)``.
2. **Output formatters** — format decompiled output (protocol: ``name`` and
   ``format(output)``).

Registration is via a ``PluginRegistry`` (explicit) or the ``@entry_point_pass``
/ ``@entry_point_formatter`` decorators, which enable file-based discovery
(``discover_from``).
"""
from __future__ import annotations

import importlib.util
import logging
import os
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Common plugin protocol."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin name."""
        ...


class AnalysisPass(Plugin):
    """Base class for graph-analysis passes."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def analyze(self, graph):
        """Analyze/annotate the graph. May return an annotated object."""
        ...


class OutputFormatter(Plugin):
    """Base class for output formatters."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def format(self, output) -> str:
        """Format a DecompOutput into text."""
        ...


class PluginRegistry:
    """Central registry for analysis passes and output formatters."""

    def __init__(self):
        self._passes: Dict[str, AnalysisPass] = {}
        self._formatters: Dict[str, OutputFormatter] = {}

    # ── Registration ──

    def register_pass(self, plugin: AnalysisPass) -> str:
        """Register an analysis pass; returns its name."""
        if not isinstance(plugin, AnalysisPass) and not hasattr(plugin, "analyze"):
            raise TypeError(f"{plugin!r} is not an AnalysisPass")
        name = plugin.name
        self._passes[name] = plugin
        logger.debug("Registered analysis pass: %s", name)
        return name

    def register_formatter(self, plugin: OutputFormatter) -> str:
        """Register an output formatter; returns its name."""
        if not hasattr(plugin, "format"):
            raise TypeError(f"{plugin!r} is not an OutputFormatter")
        name = plugin.name
        self._formatters[name] = plugin
        logger.debug("Registered output formatter: %s", name)
        return name

    # ── Lookup ──

    def pass_names(self) -> List[str]:
        return list(self._passes.keys())

    def formatter_names(self) -> List[str]:
        return list(self._formatters.keys())

    def get_pass(self, name: str) -> Optional[AnalysisPass]:
        return self._passes.get(name)

    def get_formatter(self, name: str) -> Optional[OutputFormatter]:
        return self._formatters.get(name)

    def has_pass(self, name: str) -> bool:
        return name in self._passes

    def has_formatter(self, name: str) -> bool:
        return name in self._formatters

    # ── Execution ──

    def run_passes(self, graph, names: Optional[List[str]] = None):
        """Run all (or selected) analysis passes in order over the graph."""
        targets = names if names is not None else self.pass_names()
        for name in targets:
            plugin = self._passes.get(name)
            if plugin is None:
                logger.warning("No pass named %r; skipping", name)
                continue
            try:
                graph = plugin.analyze(graph)
            except Exception as exc:  # pragma: no cover
                logger.error("Pass %r failed: %s", name, exc)
        return graph

    def format_output(self, output, name: Optional[str] = None) -> str:
        """Format output with a named formatter (default: first registered)."""
        if name is None:
            if self._formatters:
                name = next(iter(self._formatters))
            else:
                raise ValueError("No formatters registered")
        f = self._formatters.get(name)
        if f is None:
            raise KeyError(f"Unknown formatter: {name}")
        return f.format(output)

    # ── Discovery ──

    def discover_from(self, module_paths: List[str], recursive: bool = True):
        """Discover plugins from .py files (decorated with entry_point_*)."""
        for path in module_paths:
            files = []
            if os.path.isdir(path):
                if recursive:
                    for root, _dirs, names in os.walk(path):
                        for f in names:
                            if f.endswith(".py") and not f.startswith("__"):
                                files.append(os.path.join(root, f))
                else:
                    for f in os.listdir(path):
                        if f.endswith(".py") and not f.startswith("__"):
                            files.append(os.path.join(path, f))
            elif path.endswith(".py"):
                files = [path]
            for fp in files:
                self._load_module(fp)
        # Merge plugins registered by decorated modules (they register into the
        # shared default registry) into this registry.
        _shared = default_registry()
        for name, plugin in _shared._passes.items():
            if not self.has_pass(name):
                self._passes[name] = plugin
        for name, plugin in _shared._formatters.items():
            if not self.has_formatter(name):
                self._formatters[name] = plugin
        return self

    def _load_module(self, filepath: str):
        """Import a plugin module (side effect: decorators register plugins)."""
        mod_name = os.path.splitext(os.path.basename(filepath))[0]
        try:
            spec = importlib.util.spec_from_file_location(mod_name, filepath)
            if spec is None or spec.loader is None:
                return
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            logger.debug("Loaded plugin module: %s", filepath)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to load plugin %s: %s", filepath, exc)


# ── Decorators that self-register against a shared registry ──

_DEFAULT_REGISTRY = PluginRegistry()


def entry_point_pass(cls=None, *, registry: Optional[PluginRegistry] = None):
    """Class decorator: register an AnalysisPass subclass in a registry."""
    reg = registry or _DEFAULT_REGISTRY

    def wrap(klass):
        instance = klass() if isinstance(klass, type) else klass
        reg.register_pass(instance)
        return klass

    return wrap if cls is None else wrap(cls)


def entry_point_formatter(cls=None, *, registry: Optional[PluginRegistry] = None):
    """Class decorator: register an OutputFormatter subclass in a registry."""
    reg = registry or _DEFAULT_REGISTRY

    def wrap(klass):
        instance = klass() if isinstance(klass, type) else klass
        reg.register_formatter(instance)
        return klass

    return wrap if cls is None else wrap(cls)


# Shared default registry accessor
def default_registry() -> PluginRegistry:
    return _DEFAULT_REGISTRY
