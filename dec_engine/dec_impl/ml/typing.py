"""Neural type-inference pass: graph -> features -> model -> DataType.

Wraps feature extraction + the pure-Python classifier into a TypeAnalyzer
compatible with the existing pipeline. Two modes:

- ``infer``: run a trained model over a graph and annotate each variable
  with a predicted ``DataType``.
- ``train``: from labelled graphs (feature/label pairs) fit the classifier.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import dec_engine.dec_impl.ir.expression as expr
from dec_engine.dec_impl.type_inference.analyze import DataType, Size as TSize
from dec_engine.dec_impl.ml.features import (
    extract, labels_of, features_of, FEATURE_DIM,
)
from dec_engine.dec_impl.ml.classifier import OneVsRestClassifier


class NeuralTypeInferer:
    """Feature-based type inference over an IR graph."""

    def __init__(self, classes: Optional[List[str]] = None):
        self.classes = classes or ["char", "short", "int", "long", "void*"]
        self.model: Optional[OneVsRestClassifier] = None
        # store per-graph predictions: var_name -> DataType
        self.predictions: Dict[str, DataType] = {}

    def train_from_examples(self, X: List[List[float]],
                            y: List[str], epochs: int = 150):
        """Fit the classifier on raw feature/label lists."""
        self.model = OneVsRestClassifier(FEATURE_DIM, self.classes)
        self.model.train(X, y, epochs=epochs)

    def train(self, graphs, epochs: int = 150) -> float:
        """Train on labelled graphs (list of (graph, labels) pairs is not
        needed — labels come from feature extractor). Collect examples from
        graphs whose vars carry a ground-truth type in block metadata.

        Returns train accuracy.
        """
        X, y = [], []
        for graph in graphs:
            examples = extract(graph)
            X.extend(features_of(examples))
            y.extend(labels_of(examples))
        self.model = OneVsRestClassifier(FEATURE_DIM, self.classes)
        self.model.train(X, y, epochs=epochs)
        return self.model.accuracy(X, y)

    # ── inference ──

    def infer(self, graph) -> Dict[str, DataType]:
        """Predict a DataType for each variable and stash in self.predictions."""
        if self.model is None:
            raise RuntimeError("NeuralTypeInferer not trained; call train() first.")
        self.predictions = {}
        examples = extract(graph)
        for ex in examples:
            pred = self.model.predict(ex.features)
            size_bits = int(round(ex.features[0] * 64))
            self.predictions[ex.var] = _make_datatype(pred, size_bits)
        return self.predictions

    def annotate(self, graph):
        """Apply predicted types to graph block metadata."""
        preds = self.infer(graph)
        for bb in graph.blocks.values():
            bb.metadata.setdefault("ml_types", {})
            for vname, dt in preds.items():
                if vname in bb.metadata["ml_types"]:
                    continue
                bb.metadata["ml_types"][vname] = dt.name


def _make_datatype(name: str, size_bits: int) -> DataType:
    size = {8: TSize.SIZE_8, 16: TSize.SIZE_16, 32: TSize.SIZE_32,
            64: TSize.SIZE_64}.get(size_bits, TSize.AUTO)
    return DataType(name, size)
