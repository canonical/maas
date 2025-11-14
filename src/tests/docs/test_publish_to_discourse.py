# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `publish_to_discourse` module."""

from pathlib import Path

import pytest

from .helpers import load_module, TOOLS_DIR


class FakeAPI:
    """Fake Discourse API for testing."""

    def __init__(self, current: str = "old"):
        self._current = current
        self.updated = []

    def get_markdown(self, topic_id: int) -> str:
        return self._current

    def update_topic_content(self, topic_id: int, content: str) -> None:
        self.updated.append((topic_id, content))


def test_infer_mapping_from_filenames(tmp_path: Path):
    """Test that topic IDs are correctly inferred from filenames."""
    mod = load_module("_pub_mod", TOOLS_DIR / "publish_to_discourse.py")
    (tmp_path / "machines-11350.md").write_text("x", encoding="utf-8")
    (tmp_path / "status-11349.md").write_text("x", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")

    mapping = mod.infer_mapping_from_filenames(tmp_path)
    assert mapping == {"machines-11350.md": 11350, "status-11349.md": 11349}
    # Files without ID patterns are implicitly ignored (README.md not in mapping)


def test_load_markdown_content_file_not_found(tmp_path: Path):
    """Test that FileNotFoundError is raised for missing files."""
    mod = load_module("_pub_mod4", TOOLS_DIR / "publish_to_discourse.py")
    with pytest.raises(FileNotFoundError):
        mod.load_markdown_content(tmp_path, "nonexistent.md")


def test_update_topic_content_dry_run(capsys):
    """Test dry-run mode outputs without updating."""
    mod = load_module("_pub_mod5", TOOLS_DIR / "publish_to_discourse.py")
    api = FakeAPI(current="old")
    changed = mod.update_topic_content(api, 123, "new", dry_run=True)
    assert changed is True
    assert api.updated == []
    out = capsys.readouterr().out
    assert "[DRY-RUN] Would update topic 123" in out


def test_update_topic_content_skips_when_same(capsys):
    """Test that no update is made when content is identical."""
    mod = load_module("_pub_mod6", TOOLS_DIR / "publish_to_discourse.py")
    api = FakeAPI(current="same")
    changed = mod.update_topic_content(api, 5, "same", dry_run=False)
    assert changed is False
    assert api.updated == []
    out = capsys.readouterr().out
    assert "[SKIP] No changes" in out


def test_update_topic_content_updates_when_different(capsys):
    """Test that content is updated when different."""
    mod = load_module("_pub_mod7", TOOLS_DIR / "publish_to_discourse.py")
    api = FakeAPI(current="old")
    changed = mod.update_topic_content(api, 7, "new", dry_run=False)
    assert changed is True
    assert api.updated == [(7, "new")]
    out = capsys.readouterr().out
    assert "[UPDATE] Successfully updated topic 7" in out
