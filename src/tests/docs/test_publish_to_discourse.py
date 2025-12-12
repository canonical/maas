# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `publish_to_discourse` module."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile

from .helpers import load_module, TOOLS_DIR


class FakeAPI:
    """Fake Discourse API for testing."""

    def __init__(self, current="old"):
        self._current = current
        self.updated = []

    def get_markdown(self, topic_id):
        return self._current

    def update_topic_content(self, topic_id, content):
        self.updated.append((topic_id, content))


def test_infer_mapping_from_filenames():
    """Test that topic IDs are correctly inferred from filenames."""
    mod = load_module("_pub_mod", TOOLS_DIR / "publish_to_discourse.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "machines-11350.md").write_text("x", encoding="utf-8")
        (tmp_path / "status-11349.md").write_text("x", encoding="utf-8")
        (tmp_path / "README.md").write_text("x", encoding="utf-8")

        mapping = mod.infer_mapping_from_filenames(tmp_path)
        assert mapping == {
            "machines-11350.md": 11350,
            "status-11349.md": 11349,
        }


def test_load_markdown_content_file_not_found():
    """Test that FileNotFoundError is raised for missing files."""
    mod = load_module("_pub_mod4", TOOLS_DIR / "publish_to_discourse.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        try:
            mod.load_markdown_content(tmp_path, "nonexistent.md")
            raise AssertionError("Expected FileNotFoundError")
        except FileNotFoundError:
            pass


def test_update_topic_content_dry_run():
    """Test dry-run mode outputs without updating."""
    mod = load_module("_pub_mod5", TOOLS_DIR / "publish_to_discourse.py")
    api = FakeAPI(current="old")
    captured = StringIO()
    with redirect_stdout(captured):
        changed = mod.update_topic_content(api, 123, "new", dry_run=True)
    assert changed is True
    assert api.updated == []
    out = captured.getvalue()
    assert "[DRY-RUN] Would update topic 123" in out


def test_update_topic_content_skips_when_same():
    """Test that no update is made when content is identical."""
    mod = load_module("_pub_mod6", TOOLS_DIR / "publish_to_discourse.py")
    api = FakeAPI(current="same")
    captured = StringIO()
    with redirect_stdout(captured):
        changed = mod.update_topic_content(api, 5, "same", dry_run=False)
    assert changed is False
    assert api.updated == []
    out = captured.getvalue()
    assert "[SKIP] No changes" in out


def test_update_topic_content_updates_when_different():
    """Test that content is updated when different."""
    mod = load_module("_pub_mod7", TOOLS_DIR / "publish_to_discourse.py")
    api = FakeAPI(current="old")
    captured = StringIO()
    with redirect_stdout(captured):
        changed = mod.update_topic_content(api, 7, "new", dry_run=False)
    assert changed is True
    assert api.updated == [(7, "new")]
    out = captured.getvalue()
    assert "[UPDATE] Successfully updated topic 7" in out
