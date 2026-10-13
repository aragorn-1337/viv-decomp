"""PyQt6 graph viewer for decompiler CFGs.

Provides:
- ``GraphViewerWidget``: a QGraphicsView that renders a ``BlockGraph`` as
  boxes + directed edges (nodes positioned in a simple layered layout).
- ``DecompilerMainWindow``: combines the graph view with a code/JSON pane.

Works headless via ``QT_QPA_PLATFORM=offscreen`` for testing.
"""
from __future__ import annotations

import json
from typing import Optional, Dict

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QGraphicsView, QGraphicsScene,
        QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem, QSplitter,
        QPlainTextEdit, QLabel, QVBoxLayout,
    )
    from PyQt6.QtGui import QBrush, QColor, QPen, QFont, QPolygonF
    from PyQt6.QtCore import Qt, QPointF, QLineF
    _HAS_QT = True
except ImportError:  # pragma: no cover
    _HAS_QT = False

    class _Fallback:  # stub types so imports don't crash without Qt
        Qt = type("Qt", (), {})
        QPointF = type("QPointF", (), {})

    QApplication = QWidget = QMainWindow = QGraphicsView = QGraphicsScene = \
        QGraphicsRectItem = QGraphicsTextItem = QGraphicsLineItem = QSplitter = \
        QPlainTextEdit = QLabel = QVBoxLayout = _Fallback
    QBrush = QColor = QPen = QFont = QPolygonF = _Fallback
    Qt = _Fallback.Qt
    QPointF = _Fallback.QPointF


_BOX_W = 150
_BOX_H = 60
_H_X = 40
_V_Y = 90


def _layout_positions(block_addrs):
    """Simple layered layout: {addr: (x, y)} for box top-left."""
    positions = {}
    for i, addr in enumerate(block_addrs):
        positions[addr] = (i * (_BOX_W + _H_X), 0)
    return positions


class GraphViewerWidget(QGraphicsView):
    """Renders a BlockGraph as boxes + directed edges."""

    def __init__(self, graph=None, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._graph = None
        if graph is not None:
            self.set_graph(graph)

    def set_graph(self, graph):
        self._graph = graph
        self._scene.clear()
        if graph is None or not graph.blocks:
            return

        addrs = sorted(graph.blocks.keys())
        positions = _layout_positions(addrs)

        # Collect edges first so we draw lines beneath boxes
        lines = []
        for addr, block in graph.blocks.items():
            x, y = positions[addr]
            x1 = x + _BOX_W // 2
            y1 = y + _BOX_H
            for succ in getattr(block, "successors", []):
                if not hasattr(succ, "addr") or succ.addr not in positions:
                    continue
                sx, sy = positions[succ.addr]
                x2 = sx + _BOX_W // 2
                y2 = sy
                lines.append((QPointF(x1, y1), QPointF(x2, y2)))

        for p1, p2 in lines:
            pen = QPen(QColor(60, 60, 60), 1.5)
            self._scene.addLine(QLineF(p1, p2), pen)

        for addr, block in graph.blocks.items():
            x, y = positions[addr]
            rect = self._scene.addRect(
                x, y, _BOX_W, _BOX_H,
                QPen(QColor(200, 40, 40) if getattr(block, "is_entry", False)
                     else QColor(40, 40, 40), 2),
                QBrush(QColor(255, 246, 230) if getattr(block, "is_entry", False)
                       else QColor(238, 238, 255)),
            )
            rect.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
            label = getattr(block, "label", "") or f"bb_{addr:x}"
            text = self._scene.addText(label, QFont("monospace", 9))
            text.setPos(x + 6, y + 6)

        self._scene.setSceneRect(self._scene.itemsBoundingRect())
        self.fitInView(self._scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)


class DecompilerMainWindow(QMainWindow):
    """Main window combining a graph view and a code pane."""

    def __init__(self, graph=None, code: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("viv-decomp Qt Viewer")
        self.setMinimumSize(900, 600)

        splitter = QSplitter(self)
        self.graph_view = GraphViewerWidget(graph, parent=splitter)
        self.code_pane = QPlainTextEdit(splitter)
        self.code_pane.setPlainText(code)
        self.code_pane.setReadOnly(True)
        splitter.addWidget(self.graph_view)
        splitter.addWidget(self.code_pane)
        splitter.setSizes([450, 450])
        self.setCentralWidget(splitter)

    def set_graph(self, graph):
        self.graph_view.set_graph(graph)

    def set_code(self, code: str):
        self.code_pane.setPlainText(code)


def run_viewer(graph=None, code: str = "", block: bool = True) -> int:
    """Launch the Qt viewer app. Returns the Qt run exit code.

    Set ``QT_QPA_PLATFORM=offscreen`` for headless environments.
    """
    app = QApplication.instance() or QApplication([])
    win = DecompilerMainWindow(graph, code)
    win.show()
    if block:
        return app.exec()
    win.repaint()
    return 0
