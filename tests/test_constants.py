"""Tests for module-level constants and configuration."""

from tsooyts.display import (
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_CONFIG,
    DEFAULT_REMOTES,
    FUNCTION_LABELS,
    FUNCTION_NAMES,
    FUNCTION_NAMES_CONTROLS,
    FUNCTION_NAMES_DIGITS,
    ICON_DIR,
    KEYMAP_FILE,
    POSTURE_KNEEL,
    POSTURE_NONE,
    POSTURE_SIT,
    POSTURE_STAND,
    POSTURE_SYMBOLS,
    REMOTES_FILE,
)


class TestPaths:
    """Validate configuration path constants."""

    def test_config_dir_is_tsooyts(self):
        assert CONFIG_DIR.name == ".tsooyts"

    def test_config_file_in_config_dir(self):
        assert CONFIG_FILE.parent == CONFIG_DIR
        assert CONFIG_FILE.name == "config.json"

    def test_keymap_file_in_config_dir(self):
        assert KEYMAP_FILE.parent == CONFIG_DIR
        assert KEYMAP_FILE.name == "keymap.json"

    def test_remotes_file_in_config_dir(self):
        assert REMOTES_FILE.parent == CONFIG_DIR
        assert REMOTES_FILE.name == "remotes.json"

    def test_icon_dir_is_icons(self):
        assert ICON_DIR.name == "icons"


class TestDefaultConfig:
    """Validate DEFAULT_CONFIG structure and values."""

    def test_has_required_keys(self):
        required = {
            "repeat_delay_ms",
            "repeat_rate_ms",
            "max_repeats_per_sec",
            "min_page",
            "max_page",
            "book_color",
            "text_color",
            "posture_stand_color",
            "posture_sit_color",
            "posture_kneel_color",
            "posture_duration_sec",
        }
        assert required <= set(DEFAULT_CONFIG.keys())

    def test_page_range(self):
        assert DEFAULT_CONFIG["min_page"] == 1
        assert DEFAULT_CONFIG["max_page"] == 9999

    def test_repeat_values_positive(self):
        assert DEFAULT_CONFIG["repeat_delay_ms"] > 0
        assert DEFAULT_CONFIG["repeat_rate_ms"] > 0

    def test_color_values_are_hex(self):
        color_keys = [k for k in DEFAULT_CONFIG if "color" in k]
        for k in color_keys:
            v = DEFAULT_CONFIG[k]
            assert v.startswith("#"), f"{k}={v} should start with #"
            assert len(v) == 7, f"{k}={v} should be 7 chars (#rrggbb)"


class TestFunctionNames:
    """Validate function name constants."""

    def test_combined_list(self):
        assert FUNCTION_NAMES == FUNCTION_NAMES_CONTROLS + FUNCTION_NAMES_DIGITS

    def test_controls_count(self):
        assert len(FUNCTION_NAMES_CONTROLS) == 9

    def test_digits_count(self):
        assert len(FUNCTION_NAMES_DIGITS) == 10

    def test_no_duplicates(self):
        assert len(FUNCTION_NAMES) == len(set(FUNCTION_NAMES))

    def test_labels_cover_all_names(self):
        for name in FUNCTION_NAMES:
            assert name in FUNCTION_LABELS, f"Missing label for {name}"

    def test_digit_names_format(self):
        for i in range(10):
            assert f"digit_{i}" in FUNCTION_NAMES_DIGITS


class TestPostureConstants:
    """Validate posture constants."""

    def test_posture_none_is_falsy(self):
        assert not POSTURE_NONE

    def test_posture_values_are_strings(self):
        for p in (POSTURE_STAND, POSTURE_SIT, POSTURE_KNEEL):
            assert isinstance(p, str)
            assert len(p) > 0

    def test_posture_symbols_covers_all(self):
        for p in (POSTURE_NONE, POSTURE_STAND, POSTURE_SIT, POSTURE_KNEEL):
            assert p in POSTURE_SYMBOLS


class TestDefaultRemotes:
    """Validate DEFAULT_REMOTES structure."""

    def test_has_two_remotes(self):
        assert len(DEFAULT_REMOTES) == 2

    def test_hauppauge_exists(self):
        assert "Hauppauge!" in DEFAULT_REMOTES

    def test_coby_exists(self):
        assert "Coby RC-057" in DEFAULT_REMOTES

    def test_all_mappings_use_valid_functions(self):
        valid = set(FUNCTION_NAMES)
        for name, mapping in DEFAULT_REMOTES.items():
            for sc, fn in mapping.items():
                assert fn in valid, f"Remote {name}: {sc}->{fn} is not valid"

    def test_scancode_keys_are_numeric_strings(self):
        for name, mapping in DEFAULT_REMOTES.items():
            for sc in mapping.keys():
                assert sc.isdigit(), f"Remote {name}: scancode {sc!r} not numeric"
