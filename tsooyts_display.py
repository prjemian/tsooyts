#!/usr/bin/env python3
"""
Tsooyts (ցույց) Electronic Page Display

Displays page numbers and posture cues for church congregation.

Controlled via IR remote through evdev (EV_MSC/MSC_SCAN scancodes).

Created for St Paul Armenian Apostolic Church (SPAAC), Waukegan, IL.
"""

import json
import select
import sys
import threading
import time
from pathlib import Path

import evdev
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

# ---------------------------------------------------------------------------
# Configuration defaults and paths
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".tsooyts"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEYMAP_FILE = CONFIG_DIR / "keymap.json"
ICON_DIR = Path(__file__).parent

DEFAULT_CONFIG = {
    "repeat_delay_ms": 500,  # ms before key repeat begins
    "repeat_rate_ms": 200,  # ms between repeats (5/sec)
    "max_repeats_per_sec": 10,  # upper bound for settings UI
    "min_page": 1,
    "max_page": 999,
    "book_color": "#1a3a5c",  # dark blue
    "text_color": "#f0e6c8",  # warm cream/ivory
    "posture_stand_color": "#c8a84e",
    "posture_sit_color": "#6b8f6b",
    "posture_kneel_color": "#8b5e3c",
    "posture_duration_sec": 0,  # 0 = stay until toggled off
}

# Logical function names for IR mapping — split into two groups for layout
FUNCTION_NAMES_CONTROLS = [
    "page_up",  # RIGHT - increment page
    "page_down",  # LEFT  - decrement page
    "stand",  # UP    - congregation stand
    "sit",  # DOWN  - congregation sit
    "kneel",  # kneel
    "blank",  # toggle blank screen
    "enter",  # accept dialed page
    "cancel",  # cancel dialed page (LAST or STOP)
    "backspace",  # delete last digit entered
]

FUNCTION_NAMES_DIGITS = [
    "digit_0",
    "digit_1",
    "digit_2",
    "digit_3",
    "digit_4",
    "digit_5",
    "digit_6",
    "digit_7",
    "digit_8",
    "digit_9",
]

# Combined list for iteration where order doesn't matter
FUNCTION_NAMES = FUNCTION_NAMES_CONTROLS + FUNCTION_NAMES_DIGITS

FUNCTION_LABELS = {
    "page_up": "Next Page (→)",
    "page_down": "Prev Page (←)",
    "stand": "Stand (↑)",
    "sit": "Sit (↓)",
    "kneel": "Kneel",
    "blank": "Blank Screen",
    "digit_0": "0",
    "digit_1": "1",
    "digit_2": "2",
    "digit_3": "3",
    "digit_4": "4",
    "digit_5": "5",
    "digit_6": "6",
    "digit_7": "7",
    "digit_8": "8",
    "digit_9": "9",
    "enter": "Enter / Accept",
    "cancel": "Cancel (LAST/STOP)",
    "backspace": "Backspace (⌫)",
}

POSTURE_NONE = ""
POSTURE_STAND = "STAND"
POSTURE_SIT = "SIT"
POSTURE_KNEEL = "KNEEL"

POSTURE_SYMBOLS = {
    POSTURE_NONE: "",
    POSTURE_STAND: "PLEASE STAND",
    POSTURE_SIT: "PLEASE BE SEATED",
    POSTURE_KNEEL: "PLEASE KNEEL",
}


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def load_json(path, default):
    """Load JSON file or return default."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(default)


def save_json(path, data):
    """Save dict as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _colorize_pixmap(pixmap, color):
    """Return *pixmap* recolored to *color* (source must be white on transparent).

    If the source pixmap has no alpha channel the compositing would produce a
    solid-color rectangle, so we convert it to one that has alpha first.
    """
    # Ensure the source has an alpha channel for the compositing to work.
    if not pixmap.hasAlphaChannel():
        pixmap = pixmap.toImage().convertToFormat(
            QtGui.QImage.Format_ARGB32_Premultiplied
        )
        pixmap = QtGui.QPixmap.fromImage(pixmap)

    colored = QtGui.QPixmap(pixmap.size())
    colored.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(colored)
    painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
    painter.fillRect(colored.rect(), color)
    painter.setCompositionMode(QtGui.QPainter.CompositionMode_DestinationIn)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return colored


# ---------------------------------------------------------------------------
# IR Reader Thread  (evdev, EV_MSC only)
# ---------------------------------------------------------------------------


class IRReader(QtCore.QObject):
    """
    Reads raw IR scancodes from evdev input device.

    Emits scancode_received(int) for each EV_MSC / MSC_SCAN event.
    Includes built-in debounce so that held buttons don't flood
    downstream consumers (especially Teach Mode).
    """

    scancode_received = QtCore.pyqtSignal(int)

    DEFAULT_DEBOUNCE_MS = 500

    def __init__(self, config, parent=None):
        """Initialize IRReader with the given configuration dict."""
        super().__init__(parent)
        self.config = config
        self._running = False
        self._thread = None
        self._device = None
        self._debounce_ms = self.DEFAULT_DEBOUNCE_MS
        self._last_scancode = None
        self._last_emit_time = 0.0

    @property
    def debounce_ms(self):
        """Minimum milliseconds between successive emissions of the same scancode."""
        return self._debounce_ms

    @debounce_ms.setter
    def debounce_ms(self, value):
        """Set debounce interval, clamped to a minimum of 0 ms."""
        self._debounce_ms = max(0, value)

    def find_ir_device(self):
        """Find the gpio_ir_recv input device by exact name match."""
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for dev in devices:
            if dev.name == "gpio_ir_recv":
                return dev
        return None

    def start(self):
        """Start the background reader thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the reader thread to stop and close the input device."""
        self._running = False
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass

    def _run(self):
        """Main loop: find device, read EV_MSC/MSC_SCAN events, emit scancodes."""
        while self._running:
            if self._device is None:
                self._device = self.find_ir_device()
                if self._device is None:
                    time.sleep(2)
                    continue

            try:
                while self._running:
                    r, _, _ = select.select([self._device.fd], [], [], 0.5)
                    if not r:
                        continue
                    for event in self._device.read():
                        if (
                            event.type == evdev.ecodes.EV_MSC
                            and event.code == evdev.ecodes.MSC_SCAN
                        ):
                            self._debounced_emit(event.value)
            except OSError:
                self._device = None
                time.sleep(2)

    def _debounced_emit(self, scancode):
        """Emit scancode_received only if debounce interval has elapsed."""
        now = time.monotonic()
        interval = self._debounce_ms / 1000.0

        if scancode == self._last_scancode and (now - self._last_emit_time) < interval:
            return

        self._last_scancode = scancode
        self._last_emit_time = now
        self.scancode_received.emit(scancode)


# ---------------------------------------------------------------------------
# Repeat Controller
# ---------------------------------------------------------------------------


class RepeatController:
    """
    Software key-repeat with per-category behavior.

    Categories:
      - repeatable:  page_up, page_down — initial delay, then rate-limited
      - single_fire: everything else — one event per distinct press
    """

    SINGLE_FIRE_GAP_MS = 400
    REPEATABLE_FUNCTIONS = {"page_up", "page_down"}

    def __init__(self, config, lookup_fn=None):
        """
        Initialize RepeatController.

        Args:
            config: Configuration dict with repeat_delay_ms and repeat_rate_ms.
            lookup_fn: Callable mapping scancode (int) to function name (str) or None.
        """
        self.config = config
        self._lookup_fn = lookup_fn
        self._last_scancode = None
        self._first_time = 0.0
        self._last_accepted = 0.0

    def should_accept(self, scancode):
        """
        Return True if this scancode event should be dispatched.

        Applies repeat-delay and repeat-rate logic for repeatable functions,
        and a single-fire gap for all other functions.
        """
        now = time.monotonic()

        fn = self._lookup_fn(scancode) if self._lookup_fn else None
        is_repeatable = fn in self.REPEATABLE_FUNCTIONS

        if scancode != self._last_scancode:
            self._last_scancode = scancode
            self._first_time = now
            self._last_accepted = now
            return True

        if is_repeatable:
            delay = self.config.get("repeat_delay_ms", 500) / 1000.0
            rate = self.config.get("repeat_rate_ms", 200) / 1000.0
            elapsed = now - self._first_time

            if elapsed < delay:
                return False

            if now - self._last_accepted >= rate:
                self._last_accepted = now
                return True

            return False
        else:
            gap = self.SINGLE_FIRE_GAP_MS / 1000.0

            if now - self._last_accepted < gap:
                return False

            self._last_accepted = now
            return True

    def reset(self):
        """Clear the last-seen scancode, forcing the next event to be treated as a new press."""
        self._last_scancode = None


# ---------------------------------------------------------------------------
# Settings Dialog  (tabbed: Settings | Colors | Teach | Test)
# ---------------------------------------------------------------------------


class SettingsDialog(QtWidgets.QDialog):
    """Tabbed settings dialog for the tsooyts page display.

    Tabs:
        Settings  – repeat timing, posture duration
        Colors    – background, text, and posture-icon colour pickers
        Teach     – map IR remote scancodes to logical functions
        Test      – press a remote button and see its mapped function
    """

    def __init__(self, config, keymap, ir_reader, parent=None):
        """
        Initialize SettingsDialog.

        Args:
            config: Configuration dict with timing and color values.
            keymap: Dict mapping scancode strings to function names.
            ir_reader: IRReader instance for Teach / Test tabs.
            parent: Optional parent QWidget.
        """
        super().__init__(parent)
        self.config = dict(config)
        self.keymap = dict(keymap)
        self.ir_reader = ir_reader

        # Reverse map for teach tab
        self.reverse_map = {}
        for sc, fn in self.keymap.items():
            self.reverse_map[fn] = sc

        # Teach-mode listening state
        self._listening_function = None
        self._listen_start_time = 0.0
        self._listen_settle_ms = 600
        self._listen_timeout_ms = 10000
        self._listen_timer = QtCore.QTimer()
        self._listen_timer.setSingleShot(True)
        self._listen_timer.timeout.connect(self._stop_listening)
        self._row_widgets = {}

        # Compute scale factor based on screen height
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        self.screen_height = screen_size.height()
        self.scale_factor = min((self.screen_height / 600.0) ** 0.7, 1.5)

        self.setWindowTitle("tsooyts — Settings")
        self.setModal(True)
        self.setMinimumSize(int(620 * self.scale_factor), int(420 * self.scale_factor))

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        # --- Tab widget ---
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setFont(QtGui.QFont("sans-serif", int(11 * self.scale_factor)))
        outer.addWidget(self.tabs, stretch=1)

        self.tabs.addTab(self._build_settings_tab(), "Settings")
        self.tabs.addTab(self._build_colors_tab(), "Colors")
        self.tabs.addTab(self._build_teach_tab(), "Teach")
        self.tabs.addTab(self._build_test_tab(), "Test")

        # --- Save / Cancel ---
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(8)

        ok_btn = QtWidgets.QPushButton("Save")
        ok_btn.setFont(QtGui.QFont("sans-serif", int(12 * self.scale_factor)))
        ok_btn.setMinimumHeight(int(40 * self.scale_factor))
        ok_btn.clicked.connect(self._save)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setFont(QtGui.QFont("sans-serif", int(12 * self.scale_factor)))
        cancel_btn.setMinimumHeight(int(40 * self.scale_factor))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        outer.addLayout(btn_layout)

        # Connect IR signal (used by both Teach and Test tabs)
        self.ir_reader.scancode_received.connect(self._on_scancode)

    # ---- tab builders -----------------------------------------------------

    def _build_settings_tab(self):
        """Build the Settings tab: repeat delay, repeat rate, posture duration."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(6)

        sf = self.scale_factor

        # --- Repeat delay ---
        delay_label = QtWidgets.QLabel("Repeat Delay (ms before repeat starts):")
        delay_label.setFont(QtGui.QFont("sans-serif", int(11 * sf)))
        layout.addWidget(delay_label)

        self.delay_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.delay_slider.setMinimum(100)
        self.delay_slider.setMaximum(2000)
        self.delay_slider.setValue(self.config.get("repeat_delay_ms", 500))
        self.delay_slider.setTickInterval(100)
        self.delay_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        layout.addWidget(self.delay_slider)

        self.delay_value_label = QtWidgets.QLabel(f"{self.delay_slider.value()} ms")
        self.delay_value_label.setFont(QtGui.QFont("sans-serif", int(10 * sf)))
        self.delay_value_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.delay_value_label)
        self.delay_slider.valueChanged.connect(
            lambda v: self.delay_value_label.setText(f"{v} ms")
        )

        # --- Repeat rate ---
        rate_label = QtWidgets.QLabel("Repeat Rate (ms between repeats):")
        rate_label.setFont(QtGui.QFont("sans-serif", int(11 * sf)))
        layout.addWidget(rate_label)

        self.rate_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.rate_slider.setMinimum(50)
        self.rate_slider.setMaximum(1000)
        self.rate_slider.setValue(self.config.get("repeat_rate_ms", 200))
        self.rate_slider.setTickInterval(50)
        self.rate_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        layout.addWidget(self.rate_slider)

        self.rate_value_label = QtWidgets.QLabel(f"{self.rate_slider.value()} ms")
        self.rate_value_label.setFont(QtGui.QFont("sans-serif", int(10 * sf)))
        self.rate_value_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.rate_value_label)
        self.rate_slider.valueChanged.connect(
            lambda v: self.rate_value_label.setText(f"{v} ms")
        )

        # --- Posture duration ---
        posture_label = QtWidgets.QLabel("Posture Display Duration (seconds, 0 = stays on):")
        posture_label.setFont(QtGui.QFont("sans-serif", int(11 * sf)))
        layout.addWidget(posture_label)

        self.posture_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.posture_slider.setMinimum(0)
        self.posture_slider.setMaximum(120)
        self.posture_slider.setValue(self.config.get("posture_duration_sec", 0))
        self.posture_slider.setTickInterval(5)
        self.posture_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        layout.addWidget(self.posture_slider)

        posture_val = self.posture_slider.value()
        self.posture_value_label = QtWidgets.QLabel(
            "Always on" if posture_val == 0 else f"{posture_val} sec"
        )
        self.posture_value_label.setFont(QtGui.QFont("sans-serif", int(10 * sf)))
        self.posture_value_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.posture_value_label)
        self.posture_slider.valueChanged.connect(self._update_posture_label)

        layout.addStretch()

        reset_btn = QtWidgets.QPushButton("Reset to Defaults")
        reset_btn.setFont(QtGui.QFont("sans-serif", int(11 * sf)))
        reset_btn.setMinimumHeight(int(34 * sf))
        reset_btn.clicked.connect(self._reset_settings_defaults)
        layout.addWidget(reset_btn)

        return page

    def _build_colors_tab(self):
        """Build the Colors tab: background, text, and posture-icon colour pickers."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(8)

        sf = self.scale_factor

        self._color_values = {
            "book_color": self.config.get("book_color", DEFAULT_CONFIG["book_color"]),
            "text_color": self.config.get("text_color", DEFAULT_CONFIG["text_color"]),
            "posture_stand_color": self.config.get(
                "posture_stand_color", DEFAULT_CONFIG["posture_stand_color"]
            ),
            "posture_sit_color": self.config.get(
                "posture_sit_color", DEFAULT_CONFIG["posture_sit_color"]
            ),
            "posture_kneel_color": self.config.get(
                "posture_kneel_color", DEFAULT_CONFIG["posture_kneel_color"]
            ),
        }

        color_labels = {
            "book_color": "Background",
            "text_color": "Page Number",
            "posture_stand_color": "Stand Icon",
            "posture_sit_color": "Sit Icon",
            "posture_kneel_color": "Kneel Icon",
        }

        color_grid = QtWidgets.QGridLayout()
        color_grid.setSpacing(int(10 * sf))
        color_grid.setColumnStretch(0, 1)
        color_grid.setColumnStretch(1, 0)

        self._color_btns = {}
        for row, (key, display_name) in enumerate(color_labels.items()):
            lbl = QtWidgets.QLabel(f"{display_name}:")
            lbl.setFont(QtGui.QFont("sans-serif", int(12 * sf)))
            color_grid.addWidget(lbl, row, 0)

            btn = QtWidgets.QPushButton()
            btn.setFixedSize(int(100 * sf), int(36 * sf))
            self._apply_color_btn_style(btn, self._color_values[key])
            btn.clicked.connect(lambda checked, k=key: self._pick_color(k))
            color_grid.addWidget(btn, row, 1)
            self._color_btns[key] = btn

        layout.addLayout(color_grid)
        layout.addStretch()

        reset_btn = QtWidgets.QPushButton("Reset to Defaults")
        reset_btn.setFont(QtGui.QFont("sans-serif", int(11 * sf)))
        reset_btn.setMinimumHeight(int(34 * sf))
        reset_btn.clicked.connect(self._reset_colors_defaults)
        layout.addWidget(reset_btn)

        return page

    def _build_teach_tab(self):
        """Build the Teach tab: two-column grid for mapping remote buttons."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        sf = self.scale_factor

        instructions = QtWidgets.QLabel(
            'Click "Learn" next to a function, then press the remote button once.'
        )
        instructions.setFont(QtGui.QFont("sans-serif", int(10 * sf)))
        instructions.setAlignment(QtCore.Qt.AlignCenter)
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #555;")
        layout.addWidget(instructions)

        # Status bar
        self.teach_status_label = QtWidgets.QLabel("")
        self.teach_status_label.setFont(QtGui.QFont("sans-serif", int(10 * sf)))
        self.teach_status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.teach_status_label.setMinimumHeight(int(24 * sf))
        self.teach_status_label.setStyleSheet(
            "color: #ffffff; background-color: #444;"
            " border-radius: 6px; padding: 3px;"
        )
        layout.addWidget(self.teach_status_label)

        # Scroll area containing two-column layout
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        scroll_content = QtWidgets.QWidget()
        columns_layout = QtWidgets.QHBoxLayout(scroll_content)
        columns_layout.setContentsMargins(2, 2, 2, 2)
        columns_layout.setSpacing(8)

        # Left column: control functions
        left_group = QtWidgets.QGroupBox("Controls")
        left_group.setFont(QtGui.QFont("sans-serif", int(10 * sf), QtGui.QFont.Bold))
        left_grid = QtWidgets.QGridLayout(left_group)
        left_grid.setSpacing(3)
        self._populate_teach_grid(left_grid, FUNCTION_NAMES_CONTROLS)
        columns_layout.addWidget(left_group, stretch=1)

        # Right column: digit functions
        right_group = QtWidgets.QGroupBox("Digits")
        right_group.setFont(QtGui.QFont("sans-serif", int(10 * sf), QtGui.QFont.Bold))
        right_grid = QtWidgets.QGridLayout(right_group)
        right_grid.setSpacing(3)
        self._populate_teach_grid(right_grid, FUNCTION_NAMES_DIGITS)
        columns_layout.addWidget(right_group, stretch=1)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # Clear All button
        clear_all_btn = QtWidgets.QPushButton("Clear All Mappings")
        clear_all_btn.setFont(QtGui.QFont("sans-serif", int(11 * sf)))
        clear_all_btn.setMinimumHeight(int(34 * sf))
        clear_all_btn.clicked.connect(self._clear_all_mappings)
        layout.addWidget(clear_all_btn)

        return page

    def _build_test_tab(self):
        """Build the Test tab: press a remote button and see its mapped function."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(8)

        sf = self.scale_factor

        instructions = QtWidgets.QLabel(
            "Press any button on the remote to see\n"
            "what function it is mapped to."
        )
        instructions.setFont(QtGui.QFont("sans-serif", int(12 * sf)))
        instructions.setAlignment(QtCore.Qt.AlignCenter)
        instructions.setStyleSheet("color: #555;")
        layout.addWidget(instructions)

        layout.addStretch()

        self.test_scancode_label = QtWidgets.QLabel("Scancode: —")
        self.test_scancode_label.setFont(QtGui.QFont("monospace", int(16 * sf)))
        self.test_scancode_label.setAlignment(QtCore.Qt.AlignCenter)
        self.test_scancode_label.setStyleSheet(
            "background-color: #fff; border: 1px solid #ccc;"
            " border-radius: 6px; padding: 10px;"
        )
        layout.addWidget(self.test_scancode_label)

        self.test_function_label = QtWidgets.QLabel("Function: —")
        self.test_function_label.setFont(
            QtGui.QFont("sans-serif", int(20 * sf), QtGui.QFont.Bold)
        )
        self.test_function_label.setAlignment(QtCore.Qt.AlignCenter)
        self.test_function_label.setMinimumHeight(int(60 * sf))
        self.test_function_label.setStyleSheet(
            "background-color: #f0f0f0; border: 1px solid #ccc;"
            " border-radius: 6px; padding: 10px;"
        )
        layout.addWidget(self.test_function_label)

        layout.addStretch()
        return page

    # ---- teach helpers ----------------------------------------------------

    def _populate_teach_grid(self, grid, function_list):
        """Populate a grid with function rows: label, scancode, learn, clear."""
        sf = self.scale_factor
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 0)

        for row_idx, fn in enumerate(function_list):
            fn_label = QtWidgets.QLabel(FUNCTION_LABELS.get(fn, fn))
            fn_label.setFont(QtGui.QFont("sans-serif", int(10 * sf)))
            grid.addWidget(fn_label, row_idx, 0)

            sc_str = self.reverse_map.get(fn, "—")
            sc_label = QtWidgets.QLabel(sc_str)
            sc_label.setFont(QtGui.QFont("monospace", int(10 * sf)))
            sc_label.setAlignment(QtCore.Qt.AlignCenter)
            sc_label.setMinimumWidth(int(60 * sf))
            sc_label.setStyleSheet(
                "background-color: #fff; border: 1px solid #ddd;"
                " border-radius: 3px; padding: 1px 4px;"
            )
            grid.addWidget(sc_label, row_idx, 1)

            learn_btn = QtWidgets.QPushButton("Learn")
            learn_btn.setFont(QtGui.QFont("sans-serif", int(9 * sf)))
            learn_btn.setMinimumHeight(int(26 * sf))
            learn_btn.clicked.connect(lambda checked, f=fn: self._start_listening(f))
            grid.addWidget(learn_btn, row_idx, 2)

            clear_btn = QtWidgets.QPushButton("✕")
            clear_btn.setFont(QtGui.QFont("sans-serif", int(9 * sf)))
            clear_btn.setFixedWidth(int(28 * sf))
            clear_btn.setMinimumHeight(int(26 * sf))
            clear_btn.setToolTip("Remove mapping")
            clear_btn.clicked.connect(lambda checked, f=fn: self._clear_mapping(f))
            grid.addWidget(clear_btn, row_idx, 3)

            self._row_widgets[fn] = {
                "fn_label": fn_label,
                "sc_label": sc_label,
                "learn_btn": learn_btn,
                "clear_btn": clear_btn,
            }

    def _start_listening(self, function_name):
        """Begin listening for a remote button press to assign to function_name."""
        self._stop_listening()

        self._listening_function = function_name
        self._listen_start_time = time.monotonic()

        label = FUNCTION_LABELS.get(function_name, function_name)
        self.teach_status_label.setText(f"Press remote button for: {label}")
        self.teach_status_label.setStyleSheet(
            "color: #fff; background-color: #2a7ad5;"
            " border-radius: 6px; padding: 3px;"
        )

        widgets = self._row_widgets.get(function_name)
        if widgets:
            widgets["learn_btn"].setStyleSheet(
                "background-color: #2a7ad5; color: white; font-weight: bold;"
            )

        self._listen_timer.start(self._listen_timeout_ms)

    def _stop_listening(self):
        """Cancel the active listening session and update the status label."""
        self._listen_timer.stop()

        if self._listening_function:
            widgets = self._row_widgets.get(self._listening_function)
            if widgets:
                widgets["learn_btn"].setStyleSheet("")

            label = FUNCTION_LABELS.get(
                self._listening_function, self._listening_function
            )
            self.teach_status_label.setText(f"Timed out waiting for: {label}")
            self.teach_status_label.setStyleSheet(
                "color: #fff; background-color: #888;"
                " border-radius: 6px; padding: 3px;"
            )

        self._listening_function = None

    def _clear_mapping(self, function_name):
        """Remove the scancode mapping for the given function and update the UI."""
        self._stop_listening()

        if function_name in self.reverse_map:
            sc_str = self.reverse_map[function_name]
            if sc_str in self.keymap:
                del self.keymap[sc_str]
            del self.reverse_map[function_name]

        widgets = self._row_widgets.get(function_name)
        if widgets:
            widgets["sc_label"].setText("—")

        label = FUNCTION_LABELS.get(function_name, function_name)
        self.teach_status_label.setText(f"Cleared mapping for {label}")
        self.teach_status_label.setStyleSheet(
            "color: #fff; background-color: #888;"
            " border-radius: 6px; padding: 3px;"
        )

    def _clear_all_mappings(self):
        """Remove all scancode-to-function mappings and reset all scancode labels."""
        self._stop_listening()

        self.keymap.clear()
        self.reverse_map.clear()

        for fn, widgets in self._row_widgets.items():
            widgets["sc_label"].setText("—")

        self.teach_status_label.setText("Cleared all mappings")
        self.teach_status_label.setStyleSheet(
            "color: #fff; background-color: #2e8b57;"
            " border-radius: 6px; padding: 3px;"
        )

    # ---- IR scancode handler (shared by Teach + Test) ---------------------

    @QtCore.pyqtSlot(int)
    def _on_scancode(self, scancode):
        """Route incoming scancodes to the active tab's handler."""
        current_tab = self.tabs.currentIndex()

        # Teach tab (index 2): record mapping if listening
        if current_tab == 2 and self._listening_function is not None:
            elapsed_ms = (time.monotonic() - self._listen_start_time) * 1000
            if elapsed_ms < self._listen_settle_ms:
                return

            fn = self._listening_function
            sc_str = str(scancode)

            # Resolve conflicts
            conflict_fn = self.keymap.get(sc_str)
            if conflict_fn and conflict_fn != fn:
                del self.keymap[sc_str]
                if conflict_fn in self.reverse_map:
                    del self.reverse_map[conflict_fn]
                conflict_widgets = self._row_widgets.get(conflict_fn)
                if conflict_widgets:
                    conflict_widgets["sc_label"].setText("—")

            if fn in self.reverse_map:
                old_sc = self.reverse_map[fn]
                if old_sc in self.keymap:
                    del self.keymap[old_sc]

            self.keymap[sc_str] = fn
            self.reverse_map[fn] = sc_str

            widgets = self._row_widgets.get(fn)
            if widgets:
                widgets["sc_label"].setText(sc_str)
                widgets["learn_btn"].setStyleSheet("")

            label = FUNCTION_LABELS.get(fn, fn)
            self.teach_status_label.setText(
                f"Mapped scancode {scancode} -> {label}"
            )
            self.teach_status_label.setStyleSheet(
                "color: #fff; background-color: #2e8b57;"
                " border-radius: 6px; padding: 3px;"
            )

            self._listening_function = None
            self._listen_timer.stop()

        # Test tab (index 3): show result
        elif current_tab == 3:
            sc_str = str(scancode)
            self.test_scancode_label.setText(f"Scancode: {scancode}")

            fn = self.keymap.get(sc_str, None)
            if fn:
                label = FUNCTION_LABELS.get(fn, fn)
                self.test_function_label.setText(f"Mapped: {label}")
                self.test_function_label.setStyleSheet(
                    "background-color: #d4edda; border: 1px solid #28a745;"
                    " border-radius: 6px; padding: 10px;"
                    " color: #155724; font-weight: bold;"
                )
            else:
                self.test_function_label.setText("UNMAPPED")
                self.test_function_label.setStyleSheet(
                    "background-color: #f8d7da; border: 1px solid #dc3545;"
                    " border-radius: 6px; padding: 10px;"
                    " color: #721c24; font-weight: bold;"
                )

    # ---- colour helpers ---------------------------------------------------

    def _apply_color_btn_style(self, btn, color):
        """Style a color-picker button with a colored background swatch."""
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {color};"
            f" border: 2px solid #888; border-radius: 4px; }}"
            f" QPushButton:pressed {{ border: 2px solid #fff; }}"
        )

    def _pick_color(self, key):
        """Open a color dialog and update the stored color for key."""
        initial = QtGui.QColor(self._color_values[key])
        color = QtWidgets.QColorDialog.getColor(initial, self, "Choose Color")
        if color.isValid():
            self._color_values[key] = color.name()
            self._apply_color_btn_style(self._color_btns[key], color.name())

    # ---- reset helpers ----------------------------------------------------

    def _reset_settings_defaults(self):
        """Reset the Settings tab sliders to their DEFAULT_CONFIG values."""
        self.delay_slider.setValue(DEFAULT_CONFIG["repeat_delay_ms"])
        self.rate_slider.setValue(DEFAULT_CONFIG["repeat_rate_ms"])
        self.posture_slider.setValue(DEFAULT_CONFIG["posture_duration_sec"])

    def _reset_colors_defaults(self):
        """Reset the Colors tab swatches to their DEFAULT_CONFIG values."""
        for key in self._color_values:
            default = DEFAULT_CONFIG[key]
            self._color_values[key] = default
            self._apply_color_btn_style(self._color_btns[key], default)

    # ---- general helpers --------------------------------------------------

    def _update_posture_label(self, value):
        """Update the posture duration label to show 'Always on' or the value in seconds."""
        if value == 0:
            self.posture_value_label.setText("Always on")
        else:
            self.posture_value_label.setText(f"{value} sec")

    def _save(self):
        """Collect slider values and color choices into config and accept the dialog."""
        self._stop_listening()
        self.config["repeat_delay_ms"] = self.delay_slider.value()
        self.config["repeat_rate_ms"] = self.rate_slider.value()
        self.config["posture_duration_sec"] = self.posture_slider.value()
        self.config.update(self._color_values)
        self.accept()

    def get_config(self):
        """Return a copy of the current configuration dict."""
        return dict(self.config)

    def get_keymap(self):
        """Return a copy of the current scancode-to-function mapping dict."""
        return dict(self.keymap)


# ---------------------------------------------------------------------------
# Main Display Window
# ---------------------------------------------------------------------------


class MainDisplay(QtWidgets.QMainWindow):
    """
    Full-screen display showing:
      - Current page number (large, left panel) with border
      - Posture icon (right panel, vertically positioned per posture)
      - Page-entry overlay when dialing digits
    """

    def __init__(self):
        """Initialize the main display window, load config and keymap, and start IR reader."""
        super().__init__()

        # Compute scale factor based on screen height (base: 600 for 7-inch display)
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        self.screen_height = screen_size.height()
        self.scale_factor = min((self.screen_height / 600.0) ** 0.7, 1.5)

        self.config = load_json(CONFIG_FILE, DEFAULT_CONFIG)
        for k, v in DEFAULT_CONFIG.items():
            if k not in self.config:
                self.config[k] = v

        self.keymap = load_json(KEYMAP_FILE, {})

        # State
        self.current_page = 1
        self.posture = POSTURE_NONE
        self.dialing_digits = ""
        self.is_dialing = False
        self.is_blank = False
        self._settings_open = False

        # Repeat controller
        self.repeat_ctrl = RepeatController(
            self.config, lookup_fn=self._lookup_function
        )

        # IR reader
        self.ir_reader = IRReader(self.config)
        self.ir_reader.scancode_received.connect(self._on_scancode)
        self.ir_reader.debounce_ms = 50

        # Load posture icons
        self._load_posture_icons()

        # Build UI
        self._build_ui()

        # Start IR reader
        self.ir_reader.start()

        # Dial timeout timer
        self.dial_timer = QtCore.QTimer()
        self.dial_timer.setSingleShot(True)
        self.dial_timer.timeout.connect(self._cancel_dial)

        # Posture auto-clear timer
        self.posture_timer = QtCore.QTimer()
        self.posture_timer.setSingleShot(True)
        self.posture_timer.timeout.connect(self._clear_posture)

    def _build_ui(self):
        """Construct and lay out all widgets for the full-screen display."""
        self.setWindowTitle("Tsooyts Page Display")

        book_color = self.config.get("book_color", "#1a3a5c")
        text_color = self.config.get("text_color", "#f0e6c8")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background-color: {book_color};")

        # Single grid layout — all layers occupy the same cell so nothing
        # steals vertical space from the page number.
        outer = QtWidgets.QGridLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        # --- Page number / dial overlay (centred, full window) ---
        pad_px = int(10 * self.scale_factor)

        stacked = QtWidgets.QStackedWidget()

        self.page_label = QtWidgets.QLabel("1")
        self.page_label.setFont(QtGui.QFont("Monospace", int(260 * self.scale_factor), QtGui.QFont.Bold))
        self.page_label.setAlignment(QtCore.Qt.AlignCenter)
        self.page_label.setStyleSheet(
            f"color: {text_color}; padding: {pad_px}px;"
        )
        stacked.addWidget(self.page_label)

        self.dial_label = QtWidgets.QLabel("")
        self.dial_label.setFont(QtGui.QFont("Monospace", int(260 * self.scale_factor), QtGui.QFont.Bold))
        self.dial_label.setAlignment(QtCore.Qt.AlignCenter)
        self.dial_label.setStyleSheet(
            f"color: #ffffff; background-color: rgba(0,0,0,0.8);"
            f" border-radius: {int(12 * self.scale_factor)}px; padding: {int(10 * self.scale_factor)}px;"
        )
        stacked.addWidget(self.dial_label)
        stacked.setCurrentIndex(0)
        self.stacked = stacked

        outer.addWidget(stacked, 0, 0)

        # --- Posture icon (overlays right side of the same cell) ---
        icon_margin_r = int(40 * self.scale_factor)

        right_panel = QtWidgets.QWidget()
        right_panel.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.right_layout = QtWidgets.QVBoxLayout(right_panel)
        self.right_layout.setContentsMargins(0, 0, icon_margin_r, 0)
        self.right_layout.setSpacing(0)

        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.icon_label.hide()

        self.right_layout.addStretch(1)        # index 0: top spacer
        self.right_layout.addWidget(self.icon_label)  # index 1
        self.right_layout.addStretch(1)        # index 2: bottom spacer

        outer.addWidget(right_panel, 0, 0, QtCore.Qt.AlignRight)

        # --- Settings button (overlays bottom-right corner) ---
        self.settings_btn = QtWidgets.QPushButton("⚙")
        self.settings_btn.setFont(QtGui.QFont("sans-serif", 18))
        self.settings_btn.setFixedSize(50, 50)
        self.settings_btn.setStyleSheet(
            "QPushButton { background-color: rgba(255,255,255,0.15);"
            " color: #ccc; border: 1px solid #555; border-radius: 8px; }"
            " QPushButton:pressed { background-color: rgba(255,255,255,0.3); }"
        )
        self.settings_btn.clicked.connect(self._open_settings)
        outer.addWidget(
            self.settings_btn, 0, 0,
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight,
        )

        self.showFullScreen()

    def _load_posture_icons(self):
        """Load stick-figure pixmaps from ICON_DIR into self._posture_pixmaps."""
        self._posture_pixmaps = {}
        for posture, name in [
            (POSTURE_STAND, "stand"),
            (POSTURE_SIT, "sit"),
            (POSTURE_KNEEL, "kneel"),
        ]:
            path = ICON_DIR / f"{name}.png"
            pix = QtGui.QPixmap(str(path))
            self._posture_pixmaps[posture] = pix if not pix.isNull() else None

    def _update_display(self):
        """Refresh the page number, background color, and posture icon from current state."""
        book_color = self.config.get("book_color", "#1a3a5c")
        text_color = self.config.get("text_color", "#f0e6c8")

        self.centralWidget().setStyleSheet(f"background-color: {book_color};")

        pad_px = int(10 * self.scale_factor)

        if self.is_blank:
            self.page_label.setText("")
            self.page_label.setStyleSheet(
                f"color: {book_color}; padding: {pad_px}px;"
            )
            self.icon_label.hide()
            return

        self.page_label.setText(str(self.current_page))
        self.page_label.setStyleSheet(
            f"color: {text_color}; padding: {pad_px}px;"
        )

        # Posture icon — position and colorize, or hide when no posture set
        if self.posture in (POSTURE_STAND, POSTURE_SIT, POSTURE_KNEEL):
            raw = self._posture_pixmaps.get(self.posture)
            if raw:
                if self.posture == POSTURE_STAND:
                    pc = QtGui.QColor(self.config.get("posture_stand_color", "#c8a84e"))
                    self.right_layout.setStretch(0, 0)   # icon at top
                    self.right_layout.setStretch(2, 10)
                elif self.posture == POSTURE_SIT:
                    pc = QtGui.QColor(self.config.get("posture_sit_color", "#6b8f6b"))
                    self.right_layout.setStretch(0, 5)   # icon at middle
                    self.right_layout.setStretch(2, 5)
                else:  # KNEEL
                    pc = QtGui.QColor(self.config.get("posture_kneel_color", "#8b5e3c"))
                    self.right_layout.setStretch(0, 10)  # icon at bottom
                    self.right_layout.setStretch(2, 0)

                icon_w = int(120 * self.scale_factor)
                icon_h = int(240 * self.scale_factor)
                scaled = raw.scaled(
                    QtCore.QSize(icon_w, icon_h),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
                self.icon_label.setPixmap(_colorize_pixmap(scaled, pc))
                self.icon_label.show()
            else:
                self.icon_label.hide()
        else:
            self.icon_label.hide()
            self.right_layout.setStretch(0, 1)
            self.right_layout.setStretch(2, 1)

    def _lookup_function(self, scancode):
        """Return the function name mapped to scancode, or None if unmapped."""
        return self.keymap.get(str(scancode), None)

    @QtCore.pyqtSlot(int)
    def _on_scancode(self, scancode):
        """Handle a raw scancode from IRReader: look up the function and dispatch it."""
        if self._settings_open:
            return

        fn = self._lookup_function(scancode)
        if fn is None:
            return

        if not self.repeat_ctrl.should_accept(scancode):
            return

        self._dispatch(fn)

    def _dispatch(self, fn):
        """Route a logical function name to the appropriate handler method."""
        if fn == "page_up":
            self._change_page(1)
        elif fn == "page_down":
            self._change_page(-1)
        elif fn == "stand":
            self._set_posture(POSTURE_STAND)
        elif fn == "sit":
            self._set_posture(POSTURE_SIT)
        elif fn == "kneel":
            self._set_posture(POSTURE_KNEEL)
        elif fn == "blank":
            self._toggle_blank()
        elif fn.startswith("digit_"):
            digit = fn[-1]
            self._dial_digit(digit)
        elif fn == "enter":
            self._accept_dial()
        elif fn == "cancel":
            self._cancel_dial()
        elif fn == "backspace":
            self._backspace_dial()

    def _change_page(self, delta):
        """Increment or decrement the current page by delta, clamped to configured bounds.

        While blanked, the first press unblanks and shows the current page
        without changing the page number.
        """
        if self.is_dialing:
            self._cancel_dial()
        if self.is_blank:
            self.is_blank = False
            self._update_display()
            return
        min_p = self.config.get("min_page", 1)
        max_p = self.config.get("max_page", 999)
        self.current_page = max(min_p, min(max_p, self.current_page + delta))
        self._update_display()

    def _set_posture(self, posture):
        """
        Set the displayed posture cue, toggling it off if already active.

        Starts the auto-clear timer when posture_duration_sec is nonzero.
        """
        self.posture_timer.stop()

        if self.posture == posture:
            self.posture = POSTURE_NONE
        else:
            self.posture = posture

            duration = self.config.get("posture_duration_sec", 0)
            if duration > 0:
                self.posture_timer.start(duration * 1000)

        self._update_display()

    def _clear_posture(self):
        """Clear the posture cue (called by the auto-clear timer)."""
        self.posture = POSTURE_NONE
        self._update_display()

    def _toggle_blank(self):
        """Toggle blank screen mode — hides page and posture, keeps settings button."""
        self.is_blank = not self.is_blank
        self._update_display()

    def _dial_digit(self, digit):
        """Append digit to the dialing buffer and show the dial overlay."""
        self.is_blank = False
        if not self.is_dialing:
            self.is_dialing = True
            self.dialing_digits = ""
            self.stacked.setCurrentIndex(1)  # Show dial_label

        if len(self.dialing_digits) < 4:
            self.dialing_digits += digit

        self.dial_label.setText(self.dialing_digits)

        self.dial_timer.start(8000)

    def _accept_dial(self):
        """Commit the dialed digits as the new current page and hide the dial overlay."""
        self.is_blank = False
        if not self.is_dialing or not self.dialing_digits:
            self._cancel_dial()
            return

        try:
            page = int(self.dialing_digits)
        except ValueError:
            self._cancel_dial()
            return

        min_p = self.config.get("min_page", 1)
        max_p = self.config.get("max_page", 999)
        page = max(min_p, min(max_p, page))

        self.current_page = page
        self.is_dialing = False
        self.dialing_digits = ""
        self.stacked.setCurrentIndex(0)  # Show page_label
        self.dial_timer.stop()
        self._update_display()

    def _cancel_dial(self):
        """Discard the dialing buffer and hide the dial overlay."""
        self.is_dialing = False
        self.dialing_digits = ""
        self.stacked.setCurrentIndex(0)  # Show page_label
        self.dial_timer.stop()

    def _backspace_dial(self):
        """Remove the last digit from the dialing buffer, cancelling if it becomes empty."""
        if not self.is_dialing or not self.dialing_digits:
            self._cancel_dial()
            return

        self.dialing_digits = self.dialing_digits[:-1]

        if not self.dialing_digits:
            self._cancel_dial()
            return

        self.dial_label.setText(self.dialing_digits)
        self.dial_timer.start(8000)

    def _open_settings(self):
        """Open the SettingsDialog and apply any changes to config, keymap, and display."""
        if self._settings_open:
            return

        self._settings_open = True

        # Use the default debounce while settings is open so the Teach and
        # Test tabs can receive individual button presses reliably.
        old_debounce = self.ir_reader.debounce_ms
        self.ir_reader.debounce_ms = IRReader.DEFAULT_DEBOUNCE_MS

        dlg = SettingsDialog(self.config, self.keymap, self.ir_reader, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.config = dlg.get_config()
            self.keymap = dlg.get_keymap()

            self.repeat_ctrl = RepeatController(
                self.config, lookup_fn=self._lookup_function
            )

            save_json(CONFIG_FILE, self.config)
            save_json(KEYMAP_FILE, self.keymap)

            self._update_display()

        self.ir_reader.debounce_ms = old_debounce
        self._settings_open = False

    def closeEvent(self, event):
        """Stop the IR reader and persist config/keymap on window close."""
        self.ir_reader.stop()
        save_json(CONFIG_FILE, self.config)
        save_json(KEYMAP_FILE, self.keymap)
        super().closeEvent(event)

    def keyPressEvent(self, event):
        """Close the window when Escape is pressed."""
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Create the Qt application, show the full-screen display, and enter the event loop."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    app = QtWidgets.QApplication(sys.argv)

    # Hide cursor for kiosk mode
    app.setOverrideCursor(QtCore.Qt.BlankCursor)

    window = MainDisplay()
    window._update_display()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
