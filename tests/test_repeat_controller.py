"""Tests for RepeatController."""

import time

import pytest

from tsooyts.display import RepeatController


@pytest.fixture
def config():
    return {"repeat_delay_ms": 100, "repeat_rate_ms": 50}


def lookup(scancode):
    """Simple lookup: scancode 1 = page_up, 2 = page_down, others = stand."""
    return {1: "page_up", 2: "page_down"}.get(scancode, "stand")


class TestRepeatControllerBasic:
    """Basic acceptance and rejection tests."""

    def test_first_press_always_accepted(self, config):
        rc = RepeatController(config, lookup_fn=lookup)
        assert rc.should_accept(1) is True

    def test_different_scancode_always_accepted(self, config):
        rc = RepeatController(config, lookup_fn=lookup)
        assert rc.should_accept(1) is True
        assert rc.should_accept(2) is True
        assert rc.should_accept(3) is True

    def test_reset_allows_same_scancode(self, config):
        rc = RepeatController(config, lookup_fn=lookup)
        assert rc.should_accept(1) is True
        rc.reset()
        assert rc.should_accept(1) is True


class TestRepeatControllerRepeatable:
    """Tests for repeatable functions (page_up, page_down)."""

    def test_rejected_during_delay(self, config):
        rc = RepeatController(config, lookup_fn=lookup)
        assert rc.should_accept(1) is True  # initial press
        # Immediately repeat — should be within delay period
        assert rc.should_accept(1) is False

    def test_accepted_after_delay_and_rate(self, config):
        rc = RepeatController(config, lookup_fn=lookup)
        assert rc.should_accept(1) is True
        # Wait past delay (100ms) + rate (50ms)
        time.sleep(0.16)
        assert rc.should_accept(1) is True

    def test_rate_limiting(self, config):
        rc = RepeatController(config, lookup_fn=lookup)
        assert rc.should_accept(1) is True
        time.sleep(0.16)
        assert rc.should_accept(1) is True
        # Immediately after — within rate window
        assert rc.should_accept(1) is False


class TestRepeatControllerSingleFire:
    """Tests for single-fire functions (everything except page_up/page_down)."""

    def test_rejected_within_gap(self, config):
        rc = RepeatController(config, lookup_fn=lookup)
        assert rc.should_accept(99) is True  # 'stand'
        assert rc.should_accept(99) is False  # within 400ms gap

    def test_accepted_after_gap(self, config):
        rc = RepeatController(config, lookup_fn=lookup)
        assert rc.should_accept(99) is True
        time.sleep(0.45)  # > 400ms gap
        assert rc.should_accept(99) is True


class TestRepeatControllerNoLookup:
    """Tests when lookup_fn is None."""

    def test_all_treated_as_single_fire(self, config):
        rc = RepeatController(config, lookup_fn=None)
        assert rc.should_accept(1) is True
        # Without lookup, page_up scancode is treated as single-fire
        assert rc.should_accept(1) is False
