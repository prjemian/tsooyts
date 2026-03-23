"""Shared fixtures and mock setup for tsooyts tests.

On the Raspberry Pi, evdev and PyQt5 are available as system packages.
On development machines they may not be installed.  This conftest installs
lightweight stubs into sys.modules so that ``import evdev`` and
``import PyQt5`` succeed everywhere.  The stubs are *not* used when the
real packages are available.
"""

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub installer — only if the real package is missing
# ---------------------------------------------------------------------------

def _ensure_module(name, submodules=()):
    """Install a MagicMock into sys.modules for *name* if it is not importable."""
    try:
        importlib.import_module(name)
    except ImportError:
        mod = types.ModuleType(name)
        mod.__spec__ = None
        sys.modules[name] = mod

        for sub in submodules:
            fqn = f"{name}.{sub}"
            child = MagicMock()
            setattr(mod, sub, child)
            sys.modules[fqn] = child


# Ensure evdev and PyQt5 are importable
_ensure_module("evdev", submodules=["ecodes"])
_ensure_module("PyQt5", submodules=["QtCore", "QtGui", "QtWidgets"])

# Make evdev.ecodes constants available for code that references them
_evdev = sys.modules["evdev"]
if not hasattr(_evdev, "InputDevice"):
    _evdev.InputDevice = MagicMock
    _evdev.list_devices = MagicMock(return_value=[])
    _evdev_ecodes = sys.modules.get("evdev.ecodes", MagicMock())
    _evdev_ecodes.EV_MSC = 0x04
    _evdev_ecodes.MSC_SCAN = 0x04
    _evdev.ecodes = _evdev_ecodes

# Make PyQt5 stubs work for class inheritance
_qtcore = sys.modules.get("PyQt5.QtCore")
_qtwidgets = sys.modules.get("PyQt5.QtWidgets")
_qtgui = sys.modules.get("PyQt5.QtGui")

if isinstance(_qtcore, MagicMock):
    # QObject base class and signal/slot
    _qtcore.QObject = type("QObject", (), {"__init__": lambda self, *a, **kw: None})
    _qtcore.pyqtSignal = lambda *a: MagicMock()
    _qtcore.pyqtSlot = lambda *a: (lambda f: f)
    _qtcore.QTimer = MagicMock
    _qtcore.Qt = MagicMock()
    _qtcore.QSize = MagicMock

if isinstance(_qtwidgets, MagicMock):
    _qtwidgets.QDialog = type(
        "QDialog", (),
        {"__init__": lambda self, *a, **kw: None, "Accepted": 1, "Rejected": 0},
    )
    _qtwidgets.QMainWindow = type(
        "QMainWindow", (),
        {"__init__": lambda self, *a, **kw: None},
    )
    _qtwidgets.QApplication = MagicMock
    _qtwidgets.QMessageBox = MagicMock()

if isinstance(_qtgui, MagicMock):
    _qtgui.QFont = MagicMock
    _qtgui.QColor = MagicMock
    _qtgui.QPixmap = MagicMock
    _qtgui.QPainter = MagicMock
    _qtgui.QImage = MagicMock


# ---------------------------------------------------------------------------
# Detect real PyQt5 availability (before conftest stubs interfere)
# ---------------------------------------------------------------------------

import subprocess as _sp

_HAS_REAL_PYQT5 = (
    _sp.run(
        [sys.executable, "-c", "import PyQt5"],
        capture_output=True,
    ).returncode
    == 0
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_json(tmp_path):
    """Return a helper that writes JSON to a temp file and returns the Path."""
    import json

    def _write(data, name="data.json"):
        p = tmp_path / name
        p.write_text(json.dumps(data))
        return p

    return _write


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication instance for GUI tests (offscreen).

    Returns None if PyQt5 is not installed; GUI tests should check
    and skip accordingly.
    """
    if not _HAS_REAL_PYQT5:
        yield None
        return

    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt5 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    yield app


requires_pyqt5 = pytest.mark.skipif(
    not _HAS_REAL_PYQT5,
    reason="PyQt5 not installed",
)
