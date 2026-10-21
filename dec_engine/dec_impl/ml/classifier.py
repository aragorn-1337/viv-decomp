"""Pure-Python logistic-regression classifier for type prediction.

No numpy/sklearn dependency. Implements multi-class logistic regression via
one-vs-rest with plain-Python gradient descent (or a simple perceptron-ish
update). Used by the neural type-inference pass to predict C data types from
feature vectors.

Kept deliberately small and deterministic so it is testable without ML deps.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional


class BinaryLogisticModel:
    """Binary logistic regression: p(y=1|x) = sigmoid(w·x + b)."""

    def __init__(self, n_features: int, classes: Optional[tuple] = None):
        self.n_features = n_features
        self.weight = [0.0] * n_features
        self.bias = 0.0
        self.classes = classes  # (neg, pos) or None

    def _dot(self, x: List[float]) -> float:
        return sum(w * xi for w, xi in zip(self.weight, x)) + self.bias

    def sigmoid(self, z: float) -> float:
        # stable sigmoid
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        e = math.exp(z)
        return e / (1.0 + e)

    def predict_proba(self, x: List[float]) -> float:
        return self.sigmoid(self._dot(x))

    def predict(self, x: List[float]) -> int:
        return 1 if self.predict_proba(x) >= 0.5 else 0

    def train(self, X: List[List[float]], y: List[int],
              epochs: int = 200, lr: float = 0.05):
        """Gradient descent on logistic loss."""
        n = len(X)
        for _ in range(epochs):
            gw = [0.0] * self.n_features
            gb = 0.0
            for xi, yi in zip(X, y):
                p = self.sigmoid(self._dot(xi))
                err = p - yi
                gb += err
                for j in range(self.n_features):
                    gw[j] += err * xi[j]
            # average + update
            for j in range(self.n_features):
                self.weight[j] -= lr * (gw[j] / n)
            self.bias -= lr * (gb / n)

    def accuracy(self, X, y) -> float:
        if not X:
            return 0.0
        correct = sum(1 for xi, yi in zip(X, y) if self.predict(xi) == yi)
        return correct / len(X)


class OneVsRestClassifier:
    """Multi-class wrapper: one BinaryLogisticModel per class."""

    def __init__(self, n_features: int, classes: List[str]):
        self.n_features = n_features
        self.classes = classes
        self.models: Dict[str, BinaryLogisticModel] = {
            c: BinaryLogisticModel(n_features, (None, c)) for c in classes
        }

    def train(self, X: List[List[float]], y_labels: List[str],
              epochs: int = 150, lr: float = 0.05):
        for c in self.classes:
            y_bin = [1 if lab == c else 0 for lab in y_labels]
            self.models[c].train(X, y_bin, epochs=epochs, lr=lr)

    def predict_proba(self, x: List[float]) -> Dict[str, float]:
        return {c: m.predict_proba(x) for c, m in self.models.items()}

    def predict(self, x: List[float]) -> str:
        probs = self.predict_proba(x)
        return max(probs, key=probs.get)

    def accuracy(self, X, y_labels) -> float:
        if not X:
            return 0.0
        n = len(X)
        hit = sum(1 for xi, yi in zip(X, y_labels)
                  if self.predict(xi) == yi)
        return hit / n
