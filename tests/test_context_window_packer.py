"""Behavior tests for the public API of context_window_packer."""

from __future__ import annotations

import pytest

import context_window_packer


def test_normalize_trims_and_lowercases() -> None:
    assert context_window_packer.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        context_window_packer.normalize(value)


def test_version_is_semver() -> None:
    parts = context_window_packer.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
