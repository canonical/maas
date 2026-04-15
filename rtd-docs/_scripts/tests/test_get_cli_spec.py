# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maas_cli_introspection` module."""

import argparse

from get_cli_spec import (
    _get_action_form_registry,
    _get_form_field_names,
    _get_model_form_class,
    add_repo_src_to_path,
    collect_optional_rows,
    describe_parser,
    normalize_drill_down,
    normalize_positional_args,
)


def test_collect_optional_rows_filters_suppressed():
    """Test that collect_optional_rows filters out suppressed options."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--visible", help="This should appear")
    parser.add_argument("--suppressed", help=argparse.SUPPRESS)
    parser.add_argument("--another-visible", help="This should also appear")

    rows = collect_optional_rows(parser)
    option_names = {row["option"].split()[0] for row in rows}

    assert "--visible" in option_names
    assert "--another-visible" in option_names
    assert "--suppressed" not in option_names


def test_normalize_drill_down():
    """Test normalization of drill-down content."""
    drill = [
        "COMMAND",
        "machines  manage machines",
        " subnets",
        "users  manage users",
    ]
    norm_drill = normalize_drill_down(drill)
    assert "machines  manage machines" in norm_drill
    assert "users  manage users" in norm_drill


def test_normalize_drill_down_empty():
    """Test normalization of empty drill-down content."""
    empty_drill = ["COMMAND"]
    assert normalize_drill_down(empty_drill) == ""


def test_normalize_positional_args():
    """Test normalization of positional arguments."""

    positional = [
        "system_id  The system ID",
        "  continued line",
        "name",
        "  desc line",
    ]
    norm_pos = normalize_positional_args(positional)
    assert "system_id  The system ID continued line" in norm_pos
    assert "name  desc line" in norm_pos


def test_describe_parser():
    """Test that describe_parser extracts parser information correctly."""
    parser = argparse.ArgumentParser(
        description="Log in to a remote API, and remember its description and credentials."
    )
    parser.add_argument("profile_name", help="The profile name")
    parser.add_argument("url", help="The URL of the remote API")
    parser.add_argument("credentials", nargs="?", help="The credentials")

    node = describe_parser(parser, ["maas", "login"])

    assert node["key"] == "maas login"
    assert node["argv"] == ["login"]
    assert (
        "login" in node["overview"].lower()
        or "api" in node["overview"].lower()
    )
    assert len(node["options"]) >= 1


def test_get_form_field_names():
    """Test that _get_form_field_names extracts field names from forms."""

    class Form:
        declared_fields = {"field1": None, "field2": None}

    assert _get_form_field_names(Form) == {"field1", "field2"}

    class FormWithBase:
        base_fields = {"base1": None}

    assert _get_form_field_names(FormWithBase) == {"base1"}

    assert _get_form_field_names(None) == set()

    class EmptyForm:
        declared_fields = {}

    assert _get_form_field_names(EmptyForm) == set()


def test_get_model_form_class():
    """Test that _get_model_form_class extracts model_form from handlers."""

    class Form:
        pass

    class Handler:
        model_form = Form

    assert _get_model_form_class(Handler) == Form

    class HandlerNoForm:
        pass

    assert _get_model_form_class(HandlerNoForm) is None

    class HandlerNoneForm:
        model_form = None

    assert _get_model_form_class(HandlerNoneForm) is None

    class HandlerBadForm:
        model_form = "not a class"

    assert _get_model_form_class(HandlerBadForm) is None


def test_get_action_form_registry():
    """Test that _get_action_form_registry returns correct structure."""
    add_repo_src_to_path()

    registry = _get_action_form_registry()
    assert isinstance(registry, list)
    assert len(registry) > 0

    for entry in registry:
        assert len(entry) == 3
        _, action_name, _ = entry
        assert isinstance(action_name, str)
