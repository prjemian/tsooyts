"""Tests for IRReader (mocked evdev and Qt)."""

import time
from unittest.mock import MagicMock, patch

import pytest

from tsooyts.display import IRReader


@pytest.fixture
def reader():
    """Create an IRReader with default config."""
    return IRReader({"repeat_delay_ms": 500, "repeat_rate_ms": 200})


class TestDebounceProperty:
    """Tests for the debounce_ms property."""

    def test_default_debounce(self, reader):
        assert reader.debounce_ms == IRReader.DEFAULT_DEBOUNCE_MS

    def test_set_debounce(self, reader):
        reader.debounce_ms = 100
        assert reader.debounce_ms == 100

    def test_set_debounce_zero(self, reader):
        reader.debounce_ms = 0
        assert reader.debounce_ms == 0

    def test_set_debounce_negative_clamped(self, reader):
        reader.debounce_ms = -50
        assert reader.debounce_ms == 0


class TestDebouncedEmit:
    """Tests for _debounced_emit logic."""

    def test_first_emit_always_fires(self, reader):
        reader.scancode_received = MagicMock()
        reader._debounced_emit(7680)
        reader.scancode_received.emit.assert_called_once_with(7680)

    def test_same_scancode_within_interval_suppressed(self, reader):
        reader.scancode_received = MagicMock()
        reader._debounced_emit(7680)
        reader._debounced_emit(7680)  # immediately — suppressed
        assert reader.scancode_received.emit.call_count == 1

    def test_different_scancode_always_emits(self, reader):
        reader.scancode_received = MagicMock()
        reader._debounced_emit(7680)
        reader._debounced_emit(7681)
        assert reader.scancode_received.emit.call_count == 2

    def test_same_scancode_after_interval_emits(self, reader):
        reader.debounce_ms = 50
        reader.scancode_received = MagicMock()
        reader._debounced_emit(7680)
        time.sleep(0.06)
        reader._debounced_emit(7680)
        assert reader.scancode_received.emit.call_count == 2


class TestStartStop:
    """Tests for start/stop lifecycle."""

    def test_stop_sets_running_false(self, reader):
        reader._running = True
        reader.stop()
        assert reader._running is False

    def test_stop_closes_device(self, reader):
        mock_dev = MagicMock()
        reader._device = mock_dev
        reader.stop()
        mock_dev.close.assert_called_once()

    def test_stop_handles_no_device(self, reader):
        reader._device = None
        reader.stop()  # should not raise


class TestFindIrDevice:
    """Tests for find_ir_device (mocked evdev)."""

    def test_returns_none_when_no_devices(self, reader):
        with patch("tsooyts.display.evdev") as mock_evdev:
            mock_evdev.list_devices.return_value = []
            result = reader.find_ir_device()
            assert result is None

    def test_returns_device_when_found(self, reader):
        with patch("tsooyts.display.evdev") as mock_evdev:
            mock_dev = MagicMock()
            mock_dev.name = "gpio_ir_recv"
            mock_evdev.list_devices.return_value = ["/dev/input/event0"]
            mock_evdev.InputDevice.return_value = mock_dev
            result = reader.find_ir_device()
            assert result is mock_dev

    def test_skips_non_ir_devices(self, reader):
        with patch("tsooyts.display.evdev") as mock_evdev:
            mock_dev = MagicMock()
            mock_dev.name = "some_keyboard"
            mock_evdev.list_devices.return_value = ["/dev/input/event0"]
            mock_evdev.InputDevice.return_value = mock_dev
            result = reader.find_ir_device()
            assert result is None
