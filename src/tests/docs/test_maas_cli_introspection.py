# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maas_cli_introspection` module."""

import argparse

from .helpers import load_module, TOOLS_DIR


def test_collect_optional_rows_filters_suppressed():
    """Test that collect_optional_rows filters out suppressed options."""
    mod = load_module(
        "_introspect_module", TOOLS_DIR / "maas_cli_introspection.py"
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--visible", help="This should appear")
    parser.add_argument("--suppressed", help=argparse.SUPPRESS)
    parser.add_argument("--another-visible", help="This should also appear")

    rows = mod.collect_optional_rows(parser)
    option_names = {row["option"].split()[0] for row in rows}

    assert "--visible" in option_names
    assert "--another-visible" in option_names
    assert "--suppressed" not in option_names


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
    norm_drill = mod.normalize_drill_down(drill)
    assert "machines  manage machines" in norm_drill
    assert "users  manage users" in norm_drill


def test_normalize_drill_down_empty():
    """Test normalization of empty drill-down content."""
    mod = load_module(
        "_introspect_module", TOOLS_DIR / "maas_cli_introspection.py"
    )

    empty_drill = ["COMMAND"]
    assert mod.normalize_drill_down(empty_drill) == ""


def test_normalize_positional_args():
    """Test normalization of positional arguments."""
    mod = load_module(
        "_introspect_module", TOOLS_DIR / "maas_cli_introspection.py"
    )

    positional = [
        "system_id  The system ID",
        "  continued line",
        "name",
        "  desc line",
    ]
    norm_pos = mod.normalize_positional_args(positional)
    assert "system_id  The system ID continued line" in norm_pos
    assert "name  desc line" in norm_pos


def test_describe_parser():
    """Test that describe_parser extracts parser information correctly."""
    mod = load_module(
        "_introspect_module", TOOLS_DIR / "maas_cli_introspection.py"
    )

    parser = argparse.ArgumentParser(
        description="Log in to a remote API, and remember its description and credentials."
    )
    parser.add_argument("profile_name", help="The profile name")
    parser.add_argument("url", help="The URL of the remote API")
    parser.add_argument("credentials", nargs="?", help="The credentials")

    node = mod.describe_parser(parser, ["maas", "login"])

    assert node["key"] == "maas login"
    assert node["argv"] == ["login"]
    assert (
        "login" in node["overview"].lower()
        or "api" in node["overview"].lower()
    )
    assert len(node["options"]) >= 1
