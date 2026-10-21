"""Dependency-free neural-ish type inference (S8).

Lifts numeric features from Vivisect symbolik IR and predicts C data types
with a small pure-Python binary classifier (no numpy/sklearn required).

- ``features``: extract feature vectors from an IR graph / symbolik stream
- ``classifier``: pure-Python logistic-regression classifier
- ``typing``: the type-inference pass wiring graph -> features -> model -> DataType
"""
