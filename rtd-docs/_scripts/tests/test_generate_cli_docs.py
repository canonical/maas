# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `generate` module."""

from pathlib import Path
import tempfile

import pytest

# Skip Jinja2-dependent tests if Jinja2 is not available in the environment.
pytest.importorskip("jinja2")

from generate_cli_docs import (
    bold_list_leaders,
    extract_positional_args,
    find_existing_topic_number,
    format_options,
    format_positional_args,
    format_usage,
    generate_command_markdown,
    group_commands_by_resource,
    normalize_text,
    parse_keywords_text,
)
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent.parent.joinpath("_templates")


def test_normalize_text():
    """Test text normalization for markdown output."""
    txt = "\n- Name: description\n- Other: more\n  plain line\n"
    normalized = normalize_text(txt)
    assert "<br>" in normalized
    assert "|" not in normalized or "\\|" in normalized


def test_bold_list_leaders():
    """Test bolding of list item leaders."""
    bolded = bold_list_leaders("- Name: description\n  - nested: keep")
    assert "- **Name**: description" in bolded
    assert "- **nested**: keep" in bolded


def test_parse_keywords_text():
    """Test parsing of sphinx-style keyword text."""
    epilog = (
        ":param foo: first line\n"
        "  second line\n"
        ":type foo: str\n"
        ":param bar: only line\n"
        "note: not a directive\n"
    )
    out = parse_keywords_text(epilog)
    assert isinstance(out["params"], list) and len(out["params"]) == 2
    names = {p["name"] for p in out["params"]}
    assert names == {"foo", "bar"}
    foo = [p for p in out["params"] if p["name"] == "foo"][0]
    assert "second line" in foo["desc"]
    assert foo["type"] == "str"


def test_format_usage():
    """Test usage string formatting."""
    usage = (
        "usage: maas $PROFILE machines read SYSTEM_ID [options]\n"
        "\noptions:\n  -h, --help  show help\n"
    )
    formatted = format_usage(usage, "machines read")
    assert "maas" in formatted and "machines" in formatted

    assert format_usage("", "login") == "maas login [-h]"


def test_extract_positional_args():
    """Test extraction of positional arguments from usage."""
    usage = "maas $PROFILE machines read SYSTEM_ID [options]"
    args = extract_positional_args(usage, "machines read")
    assert any(
        arg.lower() in {"system_id", "system-id", "systemid"} for arg in args
    )


def test_extract_positional_args_top_level_suppressed():
    """Top-level commands should not inject positional args."""
    usage = "maas login PROFILE URL [CREDENTIALS]"
    assert extract_positional_args(usage, "login") == []


def test_format_options():
    """Test formatting of command options as markdown table."""
    table = format_options(
        [
            {"option": "-h, --help", "effect": "Show help"},
            {"option": "--foo FOO", "effect": "Foo effect"},
        ]
    )
    assert "#### Command-line options" in table
    assert "| -h, --help | Show help |" in table


def test_format_positional_args():
    """Test formatting of positional arguments as markdown table."""
    pos = format_positional_args(["system_id", "name"])
    assert "#### Positional arguments" in pos
    assert "system ID of the machine" in pos
    assert "The name of the resource" in pos


def test_group_commands_by_resource():
    """Test grouping commands by resource."""
    cmds = [
        {"key": "maas $PROFILE machines read"},
        {"key": "maas $PROFILE machines create"},
        {"key": "maas login"},
    ]
    groups = group_commands_by_resource(cmds)
    assert "machine" in groups
    assert "login" in groups


def test_find_existing_topic_number():
    """Test finding existing topic number from filename."""
    with tempfile.TemporaryDirectory() as tmpdir:
        outdir = Path(tmpdir)
        (outdir / "machines-12345.md").write_text("x", encoding="utf-8")
        (outdir / "machine-12345.md").write_text("x", encoding="utf-8")
        suffix, base_name = find_existing_topic_number("machine", outdir)
        assert suffix == "12345" and base_name in {"machine", "machines"}


def test_generate_command_markdown():
    """Test that command markdown is generated correctly."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(enabled_extensions=(".j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    command = {
        "overview": "Overview line",
        "usage": "usage: maas foo [-h]",
        "options": [{"option": "-h, --help", "effect": "show this help"}],
        "additional_sections": [
            {"title": "positional arguments", "content": "name  The name"},
            {"title": "additional_info", "content": "Final paragraph text."},
        ],
        "keywords_text": "",
        "accepts_json": False,
        "returns_json": False,
    }
    out = generate_command_markdown(env, command, "foo bar")
    pos = out.find("#### **Command-line options**")
    extra = out.find("Final paragraph text.")
    assert pos != -1 and extra != -1 and extra > pos
