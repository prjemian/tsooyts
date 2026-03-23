"""Tests for version and --version flag."""

import subprocess
import sys

import pytest


class TestVersion:
    """Tests for tsooyts.__version__."""

    def test_version_is_string(self):
        from tsooyts import __version__

        assert isinstance(__version__, str)

    def test_version_not_empty(self):
        from tsooyts import __version__

        assert len(__version__) > 0


@pytest.mark.skipif(
    subprocess.run(
        [sys.executable, "-c", "import PyQt5"],
        capture_output=True,
    ).returncode != 0,
    reason="PyQt5 not installed (subprocess check)",
)
class TestMainVersion:
    """Tests for the --version CLI flag (requires PyQt5 for module import)."""

    def test_version_flag_prints_and_exits(self):
        """Run `python -m tsooyts.display --version` and check output."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.argv = ['tsooyts', '--version']; "
             "from tsooyts.display import main; main()"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "tsooyts" in result.stdout
