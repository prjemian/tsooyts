"""Tests for MainDisplay logic (page navigation, dial, posture, blank, font sizing).

These tests require PyQt5 and run with QT_QPA_PLATFORM=offscreen.
They are skipped automatically when PyQt5 is not installed.
"""

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

requires_pyqt5 = pytest.mark.skipif(
    subprocess.run(
        [sys.executable, "-c", "import PyQt5"],
        capture_output=True,
    ).returncode != 0,
    reason="PyQt5 not installed",
)


@requires_pyqt5
class TestMainDisplayPageNavigation:
    """Tests for page navigation logic."""

    @pytest.fixture
    def display(self, qapp, tmp_path):
        """Create a MainDisplay with mocked file I/O and IR reader."""
        with (
            patch("tsooyts.display.CONFIG_DIR", tmp_path / ".tsooyts"),
            patch("tsooyts.display.CONFIG_FILE", tmp_path / "config.json"),
            patch("tsooyts.display.KEYMAP_FILE", tmp_path / "keymap.json"),
            patch("tsooyts.display.REMOTES_FILE", tmp_path / "remotes.json"),
            patch("tsooyts.display.IRReader") as MockIR,
        ):
            MockIR.return_value = MagicMock()
            MockIR.return_value.scancode_received = MagicMock()
            MockIR.return_value.scancode_received.connect = MagicMock()
            MockIR.DEFAULT_DEBOUNCE_MS = 500

            from tsooyts.display import MainDisplay

            win = MainDisplay()
            yield win
            win.close()

    def test_initial_page_is_1(self, display):
        assert display.current_page == 1

    def test_page_up(self, display):
        display._change_page(1)
        assert display.current_page == 2

    def test_page_down_clamped_at_min(self, display):
        display.current_page = 1
        display._change_page(-1)
        assert display.current_page == 1

    def test_page_up_clamped_at_max(self, display):
        display.current_page = 9999
        display._change_page(1)
        assert display.current_page == 9999

    def test_page_up_multiple(self, display):
        for _ in range(5):
            display._change_page(1)
        assert display.current_page == 6

    def test_page_down_from_middle(self, display):
        display.current_page = 50
        display._change_page(-1)
        assert display.current_page == 49

    def test_change_page_unblanks(self, display):
        display.is_blank = True
        display._change_page(1)
        assert display.is_blank is False
        # Page should not have changed (first press just unblanks)
        assert display.current_page == 1


@requires_pyqt5
class TestMainDisplayDialEntry:
    """Tests for dial (direct page entry) logic."""

    @pytest.fixture
    def display(self, qapp, tmp_path):
        with (
            patch("tsooyts.display.CONFIG_DIR", tmp_path / ".tsooyts"),
            patch("tsooyts.display.CONFIG_FILE", tmp_path / "config.json"),
            patch("tsooyts.display.KEYMAP_FILE", tmp_path / "keymap.json"),
            patch("tsooyts.display.REMOTES_FILE", tmp_path / "remotes.json"),
            patch("tsooyts.display.IRReader") as MockIR,
        ):
            MockIR.return_value = MagicMock()
            MockIR.return_value.scancode_received = MagicMock()
            MockIR.return_value.scancode_received.connect = MagicMock()
            MockIR.DEFAULT_DEBOUNCE_MS = 500

            from tsooyts.display import MainDisplay

            win = MainDisplay()
            yield win
            win.close()

    def test_dial_single_digit(self, display):
        display._dial_digit("5")
        assert display.is_dialing is True
        assert display.dialing_digits == "5"

    def test_dial_multiple_digits(self, display):
        for d in "142":
            display._dial_digit(d)
        assert display.dialing_digits == "142"

    def test_dial_max_4_digits(self, display):
        for d in "12345":
            display._dial_digit(d)
        assert display.dialing_digits == "1234"

    def test_accept_dial(self, display):
        for d in "42":
            display._dial_digit(d)
        display._accept_dial()
        assert display.current_page == 42
        assert display.is_dialing is False
        assert display.dialing_digits == ""

    def test_accept_dial_clamped_to_max(self, display):
        for d in "9999":
            display._dial_digit(d)
        display._accept_dial()
        assert display.current_page == 9999

    def test_accept_dial_clamped_to_min(self, display):
        display._dial_digit("0")
        display._accept_dial()
        assert display.current_page == 1  # clamped to min_page

    def test_cancel_dial(self, display):
        display._dial_digit("7")
        display._cancel_dial()
        assert display.is_dialing is False
        assert display.dialing_digits == ""
        assert display.current_page == 1  # unchanged

    def test_backspace_removes_last_digit(self, display):
        for d in "123":
            display._dial_digit(d)
        display._backspace_dial()
        assert display.dialing_digits == "12"

    def test_backspace_to_empty_cancels(self, display):
        display._dial_digit("5")
        display._backspace_dial()
        assert display.is_dialing is False
        assert display.dialing_digits == ""

    def test_accept_with_no_digits_cancels(self, display):
        display._accept_dial()
        assert display.is_dialing is False
        assert display.current_page == 1


@requires_pyqt5
class TestMainDisplayPosture:
    """Tests for posture cue toggling."""

    @pytest.fixture
    def display(self, qapp, tmp_path):
        with (
            patch("tsooyts.display.CONFIG_DIR", tmp_path / ".tsooyts"),
            patch("tsooyts.display.CONFIG_FILE", tmp_path / "config.json"),
            patch("tsooyts.display.KEYMAP_FILE", tmp_path / "keymap.json"),
            patch("tsooyts.display.REMOTES_FILE", tmp_path / "remotes.json"),
            patch("tsooyts.display.IRReader") as MockIR,
        ):
            MockIR.return_value = MagicMock()
            MockIR.return_value.scancode_received = MagicMock()
            MockIR.return_value.scancode_received.connect = MagicMock()
            MockIR.DEFAULT_DEBOUNCE_MS = 500

            from tsooyts.display import MainDisplay

            win = MainDisplay()
            yield win
            win.close()

    def test_set_stand(self, display):
        from tsooyts.display import POSTURE_STAND

        display._set_posture(POSTURE_STAND)
        assert display.posture == POSTURE_STAND

    def test_toggle_stand_off(self, display):
        from tsooyts.display import POSTURE_NONE, POSTURE_STAND

        display._set_posture(POSTURE_STAND)
        display._set_posture(POSTURE_STAND)  # toggle off
        assert display.posture == POSTURE_NONE

    def test_switch_postures(self, display):
        from tsooyts.display import POSTURE_KNEEL, POSTURE_SIT, POSTURE_STAND

        display._set_posture(POSTURE_STAND)
        display._set_posture(POSTURE_SIT)
        assert display.posture == POSTURE_SIT
        display._set_posture(POSTURE_KNEEL)
        assert display.posture == POSTURE_KNEEL

    def test_clear_posture(self, display):
        from tsooyts.display import POSTURE_NONE, POSTURE_STAND

        display._set_posture(POSTURE_STAND)
        display._clear_posture()
        assert display.posture == POSTURE_NONE


@requires_pyqt5
class TestMainDisplayBlank:
    """Tests for blank screen toggling."""

    @pytest.fixture
    def display(self, qapp, tmp_path):
        with (
            patch("tsooyts.display.CONFIG_DIR", tmp_path / ".tsooyts"),
            patch("tsooyts.display.CONFIG_FILE", tmp_path / "config.json"),
            patch("tsooyts.display.KEYMAP_FILE", tmp_path / "keymap.json"),
            patch("tsooyts.display.REMOTES_FILE", tmp_path / "remotes.json"),
            patch("tsooyts.display.IRReader") as MockIR,
        ):
            MockIR.return_value = MagicMock()
            MockIR.return_value.scancode_received = MagicMock()
            MockIR.return_value.scancode_received.connect = MagicMock()
            MockIR.DEFAULT_DEBOUNCE_MS = 500

            from tsooyts.display import MainDisplay

            win = MainDisplay()
            yield win
            win.close()

    def test_toggle_blank_on(self, display):
        display._toggle_blank()
        assert display.is_blank is True

    def test_toggle_blank_off(self, display):
        display._toggle_blank()
        display._toggle_blank()
        assert display.is_blank is False

    def test_page_preserved_after_blank(self, display):
        display.current_page = 42
        display._toggle_blank()
        display._toggle_blank()
        assert display.current_page == 42


@requires_pyqt5
class TestMainDisplayFontSizing:
    """Tests for _font_size_for_digits."""

    @pytest.fixture
    def display(self, qapp, tmp_path):
        with (
            patch("tsooyts.display.CONFIG_DIR", tmp_path / ".tsooyts"),
            patch("tsooyts.display.CONFIG_FILE", tmp_path / "config.json"),
            patch("tsooyts.display.KEYMAP_FILE", tmp_path / "keymap.json"),
            patch("tsooyts.display.REMOTES_FILE", tmp_path / "remotes.json"),
            patch("tsooyts.display.IRReader") as MockIR,
        ):
            MockIR.return_value = MagicMock()
            MockIR.return_value.scancode_received = MagicMock()
            MockIR.return_value.scancode_received.connect = MagicMock()
            MockIR.DEFAULT_DEBOUNCE_MS = 500

            from tsooyts.display import MainDisplay

            win = MainDisplay()
            yield win
            win.close()

    def test_1_digit_uses_large_font(self, display):
        size = display._font_size_for_digits(1)
        assert size == int(260 * display.scale_factor)

    def test_3_digits_uses_large_font(self, display):
        size = display._font_size_for_digits(3)
        assert size == int(260 * display.scale_factor)

    def test_4_digits_uses_smaller_font(self, display):
        size = display._font_size_for_digits(4)
        assert size == int(150 * display.scale_factor)

    def test_4_digit_smaller_than_3_digit(self, display):
        assert display._font_size_for_digits(4) < display._font_size_for_digits(3)

    def test_5_digits_uses_smallest(self, display):
        size = display._font_size_for_digits(5)
        assert size == int(150 * display.scale_factor)


@requires_pyqt5
class TestMainDisplayDispatch:
    """Tests for _dispatch routing."""

    @pytest.fixture
    def display(self, qapp, tmp_path):
        with (
            patch("tsooyts.display.CONFIG_DIR", tmp_path / ".tsooyts"),
            patch("tsooyts.display.CONFIG_FILE", tmp_path / "config.json"),
            patch("tsooyts.display.KEYMAP_FILE", tmp_path / "keymap.json"),
            patch("tsooyts.display.REMOTES_FILE", tmp_path / "remotes.json"),
            patch("tsooyts.display.IRReader") as MockIR,
        ):
            MockIR.return_value = MagicMock()
            MockIR.return_value.scancode_received = MagicMock()
            MockIR.return_value.scancode_received.connect = MagicMock()
            MockIR.DEFAULT_DEBOUNCE_MS = 500

            from tsooyts.display import MainDisplay

            win = MainDisplay()
            yield win
            win.close()

    def test_dispatch_page_up(self, display):
        display._dispatch("page_up")
        assert display.current_page == 2

    def test_dispatch_page_down(self, display):
        display.current_page = 10
        display._dispatch("page_down")
        assert display.current_page == 9

    def test_dispatch_stand(self, display):
        from tsooyts.display import POSTURE_STAND

        display._dispatch("stand")
        assert display.posture == POSTURE_STAND

    def test_dispatch_digit(self, display):
        display._dispatch("digit_3")
        assert display.is_dialing is True
        assert display.dialing_digits == "3"

    def test_dispatch_enter_after_dial(self, display):
        display._dispatch("digit_5")
        display._dispatch("digit_0")
        display._dispatch("enter")
        assert display.current_page == 50

    def test_dispatch_cancel(self, display):
        display._dispatch("digit_1")
        display._dispatch("cancel")
        assert display.is_dialing is False

    def test_dispatch_blank(self, display):
        display._dispatch("blank")
        assert display.is_blank is True

    def test_dispatch_backspace(self, display):
        display._dispatch("digit_1")
        display._dispatch("digit_2")
        display._dispatch("backspace")
        assert display.dialing_digits == "1"


@requires_pyqt5
class TestMainDisplayLookup:
    """Tests for _lookup_function."""

    @pytest.fixture
    def display(self, qapp, tmp_path):
        with (
            patch("tsooyts.display.CONFIG_DIR", tmp_path / ".tsooyts"),
            patch("tsooyts.display.CONFIG_FILE", tmp_path / "config.json"),
            patch("tsooyts.display.KEYMAP_FILE", tmp_path / "keymap.json"),
            patch("tsooyts.display.REMOTES_FILE", tmp_path / "remotes.json"),
            patch("tsooyts.display.IRReader") as MockIR,
        ):
            MockIR.return_value = MagicMock()
            MockIR.return_value.scancode_received = MagicMock()
            MockIR.return_value.scancode_received.connect = MagicMock()
            MockIR.DEFAULT_DEBOUNCE_MS = 500

            from tsooyts.display import MainDisplay

            win = MainDisplay()
            yield win
            win.close()

    def test_mapped_scancode(self, display):
        display.keymap = {"7703": "page_up"}
        assert display._lookup_function(7703) == "page_up"

    def test_unmapped_scancode(self, display):
        display.keymap = {}
        assert display._lookup_function(9999) is None
