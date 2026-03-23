"""Tests for SettingsDialog keymap, remotes, and recognize logic.

These tests require PyQt5 and run with QT_QPA_PLATFORM=offscreen.
They are skipped automatically when PyQt5 is not installed.
"""

from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import requires_pyqt5


def _make_mock_ir_reader():
    """Create a mock IRReader with the expected interface."""
    ir = MagicMock()
    ir.scancode_received = MagicMock()
    ir.scancode_received.connect = MagicMock()
    ir.scancode_received.disconnect = MagicMock()
    ir.DEFAULT_DEBOUNCE_MS = 500
    ir.debounce_ms = 500
    return ir


@requires_pyqt5
class TestSettingsDialogKeymap:
    """Tests for keymap management in SettingsDialog."""

    @pytest.fixture
    def dlg(self, qapp):
        from tsooyts.display import DEFAULT_CONFIG, SettingsDialog

        config = dict(DEFAULT_CONFIG)
        keymap = {"7703": "page_up", "7702": "page_down"}
        remotes = {}
        ir = _make_mock_ir_reader()
        dialog = SettingsDialog(config, keymap, remotes, ir)
        yield dialog
        dialog.close()

    def test_initial_keymap_copy(self, dlg):
        assert dlg.keymap == {"7703": "page_up", "7702": "page_down"}

    def test_get_keymap_returns_copy(self, dlg):
        km = dlg.get_keymap()
        assert km == dlg.keymap
        assert km is not dlg.keymap

    def test_reverse_map_built(self, dlg):
        assert dlg.reverse_map["page_up"] == "7703"
        assert dlg.reverse_map["page_down"] == "7702"

    def test_clear_mapping(self, dlg):
        dlg._clear_mapping("page_up")
        assert "7703" not in dlg.keymap
        assert "page_up" not in dlg.reverse_map

    def test_clear_all_mappings(self, dlg):
        # Mock the confirmation dialog to return Yes
        from PyQt5 import QtWidgets

        with patch.object(
            QtWidgets.QMessageBox, "question", return_value=QtWidgets.QMessageBox.Yes
        ):
            dlg._clear_all_mappings()
        assert len(dlg.keymap) == 0
        assert len(dlg.reverse_map) == 0

    def test_clear_all_mappings_cancelled(self, dlg):
        from PyQt5 import QtWidgets

        with patch.object(
            QtWidgets.QMessageBox, "question", return_value=QtWidgets.QMessageBox.No
        ):
            dlg._clear_all_mappings()
        # Mappings should be unchanged
        assert len(dlg.keymap) == 2


@requires_pyqt5
class TestSettingsDialogRemotes:
    """Tests for remotes collection management."""

    @pytest.fixture
    def dlg(self, qapp):
        from tsooyts.display import DEFAULT_CONFIG, SettingsDialog

        config = dict(DEFAULT_CONFIG)
        keymap = {"7703": "page_up", "7702": "page_down"}
        remotes = {
            "Remote A": {"100": "page_up", "101": "page_down"},
            "Remote B": {"200": "page_up", "201": "page_down"},
        }
        ir = _make_mock_ir_reader()
        dialog = SettingsDialog(config, keymap, remotes, ir)
        yield dialog
        dialog.close()

    def test_remotes_loaded(self, dlg):
        assert "Remote A" in dlg.remotes
        assert "Remote B" in dlg.remotes

    def test_get_remotes_returns_copy(self, dlg):
        r = dlg.get_remotes()
        assert r == dlg.remotes
        assert r is not dlg.remotes

    def test_use_recognized_remote_loads_keymap(self, dlg):
        dlg._recog_selected_name = "Remote A"
        dlg._use_recognized_remote()
        assert dlg.keymap == {"100": "page_up", "101": "page_down"}
        assert dlg.reverse_map["page_up"] == "100"
        assert dlg.reverse_map["page_down"] == "101"

    def test_use_recognized_remote_with_no_selection(self, dlg):
        original_keymap = dict(dlg.keymap)
        dlg._recog_selected_name = None
        dlg._use_recognized_remote()
        assert dlg.keymap == original_keymap

    def test_select_remote(self, dlg):
        dlg._select_remote("Remote B")
        assert dlg._recog_selected_name == "Remote B"


@requires_pyqt5
class TestSettingsDialogRecognize:
    """Tests for the Recognize tab scoring logic."""

    @pytest.fixture
    def dlg(self, qapp):
        from tsooyts.display import DEFAULT_CONFIG, SettingsDialog

        config = dict(DEFAULT_CONFIG)
        keymap = {}
        remotes = {
            "Remote A": {"100": "page_up", "101": "page_down", "102": "stand"},
            "Remote B": {"200": "digit_0", "201": "digit_1"},
        }
        ir = _make_mock_ir_reader()
        dialog = SettingsDialog(config, keymap, remotes, ir)
        yield dialog
        dialog.close()

    def test_initial_recognize_state(self, dlg):
        assert len(dlg._recog_scancodes) == 0
        assert dlg._recog_selected_name is None

    def test_reset_recognize(self, dlg):
        dlg._recog_scancodes.add("100")
        dlg._recog_selected_name = "Remote A"
        dlg._reset_recognize()
        assert len(dlg._recog_scancodes) == 0
        assert dlg._recog_selected_name is None

    def test_recognize_scoring_matches_correct_remote(self, dlg):
        # Simulate pressing buttons from Remote A
        dlg._recog_scancodes = {"100", "101"}
        dlg._update_recognize_results()
        # Check that results were generated (widgets added to layout)
        assert dlg.recog_results_layout.count() > 0

    def test_recognize_no_matches_with_unknown_scancodes(self, dlg):
        dlg._recog_scancodes = {"999", "998"}
        dlg._update_recognize_results()
        # No results should appear (0 hits for all remotes)
        assert dlg.recog_results_layout.count() == 0


@requires_pyqt5
class TestSettingsDialogSave:
    """Tests for the _save method."""

    @pytest.fixture
    def dlg(self, qapp):
        from tsooyts.display import DEFAULT_CONFIG, SettingsDialog

        config = dict(DEFAULT_CONFIG)
        keymap = {"7703": "page_up", "7702": "page_down"}
        remotes = {}
        ir = _make_mock_ir_reader()
        dialog = SettingsDialog(config, keymap, remotes, ir)
        yield dialog
        dialog.close()

    def test_save_stores_keymap_in_remotes(self, dlg):
        # Mock accept() to prevent dialog from actually closing
        with patch.object(dlg, "accept"):
            dlg._save()
        # The current keymap should be stored in remotes under some name
        assert len(dlg.remotes) == 1
        stored = list(dlg.remotes.values())[0]
        assert stored == {"7703": "page_up", "7702": "page_down"}

    def test_save_updates_existing_remote(self, dlg):
        # First save
        with patch.object(dlg, "accept"):
            dlg._save()
        assert len(dlg.remotes) == 1
        # Modify a mapping but keep same scancode set
        dlg.keymap["7703"] = "page_down"
        dlg.keymap["7702"] = "page_up"
        with patch.object(dlg, "accept"):
            dlg._save()
        # Should update in place, not create a second entry
        assert len(dlg.remotes) == 1

    def test_save_collects_slider_values(self, dlg):
        dlg.delay_slider.setValue(300)
        dlg.rate_slider.setValue(100)
        dlg.posture_slider.setValue(5)
        with patch.object(dlg, "accept"):
            dlg._save()
        assert dlg.config["repeat_delay_ms"] == 300
        assert dlg.config["repeat_rate_ms"] == 100
        assert dlg.config["posture_duration_sec"] == 5

    def test_save_empty_keymap_not_stored(self, dlg):
        dlg.keymap.clear()
        with patch.object(dlg, "accept"):
            dlg._save()
        assert len(dlg.remotes) == 0
