# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maas_cli_introspection` module."""

import argparse
import types

from .helpers import load_module, TOOLS_DIR


def _fake_completed_process(text: str):
    return types.SimpleNamespace(stdout=text, stderr="", returncode=0)


def test_normalize_drill_down():
    """Test normalization of drill-down content."""
    mod = load_module(
        "_introspect_module", TOOLS_DIR / "maas_cli_introspection.py"
    )

    drill = [
        "COMMAND",
        "machines  manage machines",
        " subnets",
        "users  manage users",
    ]
    norm_drill = mod._normalize_drill_down(drill)
    assert "machines  manage machines" in norm_drill
    assert "users  manage users" in norm_drill


def test_normalize_drill_down_empty():
    """Test normalization of empty drill-down content."""
    mod = load_module(
        "_introspect_module2", TOOLS_DIR / "maas_cli_introspection.py"
    )

    empty_drill = ["COMMAND"]
    assert mod._normalize_drill_down(empty_drill) == ""


def test_normalize_positional_args():
    """Test normalization of positional arguments."""
    mod = load_module(
        "_introspect_module3", TOOLS_DIR / "maas_cli_introspection.py"
    )

    positional = [
        "system_id  The system ID",
        "  continued line",
        "name",
        "  desc line",
    ]
    norm_pos = mod._normalize_positional_args(positional)
    assert "system_id  The system ID continued line" in norm_pos
    assert "name  desc line" in norm_pos


def test_normalize_positional_args_no_description():
    """Test normalization of positional args without descriptions."""
    mod = load_module(
        "_introspect_module4", TOOLS_DIR / "maas_cli_introspection.py"
    )

    no_desc = ["system_id"]
    norm_no_desc = mod._normalize_positional_args(no_desc)
    assert "system_id" in norm_no_desc


def test_describe_parser_trailing_prose_and_filters(monkeypatch):
    """Ensure trailing prose is captured as a paragraph and no -h duplication."""
    mod = load_module(
        "_introspect_module5", TOOLS_DIR / "maas_cli_introspection.py"
    )

    help_text = (
        "usage: maas login [-h] profile-name url [credentials]\n\n"
        "Log in to a remote API, and remember its description and credentials.\n\n"
        "positional arguments:\n"
        "  profile-name  The name with which you will later refer to this remote\n"
        "                server and credentials within this tool.\n"
        "  url           The URL of the remote API\n\n"
        "options:\n"
        "  -h, --help    show this help message and exit\n\n"
        "If credentials are not provided on the command-line, they will be\n"
        "prompted for interactively.\n"
    )

    # Monkeypatch subprocess.run to return the sample `-h` output above
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *a, **kw: _fake_completed_process(help_text),
    )

    parser = argparse.ArgumentParser(
        description="Log in to a remote API, and remember its description and credentials."
    )
    node = mod.describe_parser(parser, ["maas", "login"])

    sections = {
        s["title"].strip().lower(): s["content"]
        for s in node["additional_sections"]
    }
    assert "positional arguments" in sections
    assert "profile-name" in sections["positional arguments"]
    # Trailing prose should be captured somewhere and should not duplicate -h
    if "additional_info" in sections:
        extra = sections["additional_info"]
        assert "-h, --help" not in extra
        assert "prompted for interactively" in extra
    else:
        # Fallback: ensure the trailing prose is captured somewhere
        combined = "\n".join(sections.values())
        assert "prompted for interactively" in combined
