"""Plugin analysis pass exposing neural type inference to the pipeline.

Registers the ML type inferer as a plugin ``AnalysisPass`` so it can be run
like any other pass. When no trained model exists it falls back to the
existing size-based TypeAnalyzer (no-op for the IR if ML unavailable).
"""
from __future__ import annotations

from typing import Optional

from dec_engine.dec_impl.plugin.registry import AnalysisPass


class NeuralTypePass(AnalysisPass):
    """Runs the neural type inferer over the graph, annotating each block."""

    name = "neural_types"

    def __init__(self, inferer=None):
        self._inferer = inferer  # optional pre-trained NeuralTypeInferer

    def analyze(self, graph):
        from dec_engine.dec_impl.ml.typing import NeuralTypeInferer

        inferer = self._inferer if self._inferer is not None else NeuralTypeInferer()
        # If no trained model, the inference would throw — degrade to size-based.
        if inferer.model is None:
            return graph  # skip; existing size-based pass handles it
        try:
            inferer.annotate(graph)
        except Exception as exc:  # pragma: no cover
            __import__("logging").getLogger(__name__).debug(
                "neural_types pass skipped: %s", exc)
        return graph
