"""Vivisect extension: decompile functions with the viv-decomp pipeline.

Drop this module (or symlink it) anywhere on ``VIV_EXT_PATH`` and Vivisect will
call ``vivExtension(vw, vwgui)`` on startup. It:

- Adds a menu entry under **Decompile -> Decompile function** that decompiles
  the function containing the current cursor address.
- Adds a dock widget showing the decompiled C output, plus a CFG graph pane
  when the PyQt6 binding is available.

It consumes the **live workspace** ``vw`` via
``VivisectDecompiler.from_workspace`` — no binary re-load, so the
``analyzePLT`` load quirk never occurs.

Newer Vivisect uses PyQt6; older builds use PyQt5. Both bindings are supported
(PyQt6 preferred). Falls back gracefully if no Qt GUI is present (headless).
"""
from __future__ import annotations

import logging

logger = logging.getLogger("viv-decomp.ext")

# Prefer PyQt6 (newer Vivisect), fall back to PyQt5 (older builds).
try:
    from PyQt6.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QSplitter
    from PyQt6.QtCore import Qt as _Qt
    _QT = "PyQt6"
except ImportError:  # pragma: no cover
    try:
        from PyQt5.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QSplitter
        from PyQt5.QtCore import Qt as _Qt
        _QT = "PyQt5"
    except ImportError:  # pragma: no cover
        logger.warning("No Qt binding available; decompiler extension headless")
        _QT = None
        QTextEdit = QWidget = QVBoxLayout = QSplitter = None
        _Qt = None


def _decompile_text(decomp, funcva):
    """Decompile funcva from a decompiler bound to the live vw."""
    out = decomp.decompile_address(funcva)
    return out.text if out and out.text else "// error"


def _func_at(vw, va):
    """Return the function entry address for va (prefer exact entry).

    ``vw.getFunction(va)`` returns the function entry when ``va`` is itself a
    function entry (Vivisect's API). If missing, fall back to the nearest
    entry <= va from the function list.
    """
    try:
        entry = vw.getFunction(va)
        if entry is not None:
            return entry
    except Exception:
        pass
    # Nearest entry <= va from the known function set.
    try:
        candidates = [f for f in vw.getFunctions() if f <= va]
        if candidates:
            return max(candidates)
    except Exception:
        pass
    return None


def _make_dock(vw, vwgui):
    """Create a dock widget; returns the window or None when headless."""
    if _QT is None:
        return None

    # parent=None: the docking system reparents the widget under vwgui.
    window = QWidget(parent=None)
    window.setWindowTitle("viv-decomp")

    text = QTextEdit(parent=window)
    text.setReadOnly(True)
    text.setPlainText("Select a function address, then Decompile.")

    window._text = text
    window._vw = vw

    if _QT == "PyQt6":
        # Add a graph pane for the graph viewer (PyQt6 build).
        try:
            from viv_decomp.qt_viewer import GraphViewerWidget
            split = QSplitter(window)
            graph = GraphViewerWidget(parent=split)
            split.addWidget(graph)
            split.addWidget(text)
            layout = QVBoxLayout(window)
            layout.addWidget(split)
            window._graph = graph
            window._set_graph = graph.set_graph
        except Exception:
            layout = QVBoxLayout(window)
            layout.addWidget(text)
    else:
        layout = QVBoxLayout(window)
        layout.addWidget(text)

    return window


def vivExtension(vw, vwgui):
    """Vivisect entry point (called once per loaded extension)."""
    from viv_decomp.decompiler import VivisectDecompiler
    vw._vvd_decomp = VivisectDecompiler.from_workspace(vw)

    def do_decompile(_=None):
        try:
            va = getattr(vwgui, "getVa", lambda: 0)()
            fva = _func_at(vw, va) or va
            code = _decompile_text(vw._vvd_decomp, fva)

            # Build the graph for the graph pane (live workspace, no re-load)
            graph = vw._vvd_decomp.graph_builder.get_graph(fva)

            name = vw.getName(fva) or f"func_{fva:x}"
            header = f"// {name} @ 0x{fva:x}\n\n{code}"
            for dock_widget, _dw in vwgui.vqGetDockWidgetsByName("viv-decomp"):
                window = dock_widget
                if hasattr(window, "_text"):
                    window._text.setPlainText(header)
                if hasattr(window, "_set_graph"):
                    window._set_graph(graph)
        except Exception as exc:  # pragma: no cover
            vw.vprint(f"viv-decomp error: {type(exc).__name__}: {exc}")

    # Menu entry
    if hasattr(vwgui, "vqAddMenuField"):
        vwgui.vqAddMenuField("&Decompile.&Decompile Function", do_decompile)

    # Dock widget
    dock = _make_dock(vw, vwgui)
    if dock is not None and hasattr(vwgui, "vqDockWidget"):
        d = vwgui.vqDockWidget(dock, floating=True)
        d.resize(420, 360)
        vw.vprint("viv-decomp extension loaded")
    else:
        vw.vprint("viv-decomp extension loaded (headless)")


# Allow running as a standalone GUI-less smoke check: python viv_extension.py
if __name__ == "__main__":  # pragma: no cover
    print(f"viv-decomp Vivisect extension (_QT={_QT}).")
    print("Place this file on VIV_EXT_PATH and restart Vivisect to load.")
