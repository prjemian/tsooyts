"""Tests for load_json and save_json helper functions."""

import json

import pytest

from tsooyts.display import load_json, save_json


class TestLoadJson:
    """Tests for load_json."""

    def test_loads_valid_json(self, tmp_json):
        data = {"key": "value", "number": 42}
        path = tmp_json(data)
        result = load_json(path, {})
        assert result == data

    def test_returns_default_on_missing_file(self, tmp_path):
        missing = tmp_path / "no_such_file.json"
        default = {"fallback": True}
        result = load_json(missing, default)
        assert result == default

    def test_returns_copy_of_default(self, tmp_path):
        missing = tmp_path / "no_such_file.json"
        default = {"fallback": True}
        result = load_json(missing, default)
        assert result is not default

    def test_returns_default_on_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json {{{")
        default = {"fallback": True}
        result = load_json(bad, default)
        assert result == default

    def test_returns_default_on_empty_file(self, tmp_path):
        empty = tmp_path / "empty.json"
        empty.write_text("")
        result = load_json(empty, {"x": 1})
        assert result == {"x": 1}


class TestSaveJson:
    """Tests for save_json."""

    def test_writes_valid_json(self, tmp_path):
        path = tmp_path / "out.json"
        data = {"hello": "world"}
        save_json(path, data)
        assert json.loads(path.read_text()) == data

    def test_creates_parent_directories(self, tmp_path):
        path = tmp_path / "a" / "b" / "c" / "out.json"
        save_json(path, {"nested": True})
        assert path.exists()
        assert json.loads(path.read_text()) == {"nested": True}

    def test_overwrites_existing_file(self, tmp_path):
        path = tmp_path / "out.json"
        save_json(path, {"first": 1})
        save_json(path, {"second": 2})
        assert json.loads(path.read_text()) == {"second": 2}

    def test_roundtrip_with_load_json(self, tmp_path):
        path = tmp_path / "roundtrip.json"
        original = {"a": [1, 2, 3], "b": {"nested": True}}
        save_json(path, original)
        loaded = load_json(path, {})
        assert loaded == original

    def test_indented_output(self, tmp_path):
        path = tmp_path / "indented.json"
        save_json(path, {"key": "value"})
        text = path.read_text()
        assert "\n" in text  # indented means multi-line
