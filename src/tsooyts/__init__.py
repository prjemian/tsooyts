"""Tsooyts (ցույց) — Electronic page display for church congregations."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

try:
    __version__ = version("tsooyts")
except PackageNotFoundError:
    __version__ = "0.0.0"
