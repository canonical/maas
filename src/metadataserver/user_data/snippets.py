# Copyright 2013-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Low-level routines for access to snippets.

These are used by the user-data code, but also by `setup.py`.  That's why
importing this must not pull in any unnecessary framework modules etc.
"""

__all__ = [
    "list_snippets",
    "read_snippet",
    "strip_name",
    "get_snippet_context",
    "get_userdata_template_dir",
]

import os

from provisioningserver.utils.fs import read_text_file


def get_userdata_template_dir():
    """Return the absolute location of the userdata
    template directory."""
    return os.path.join(os.path.dirname(__file__), "templates")


def get_snippet_context(snippets_dir=None, encoding="utf-8"):
    """Return the context of all of the snippets."""
    if snippets_dir is None:
        snippets_dir = os.path.join(get_userdata_template_dir(), "snippets")
    snippets = {
        strip_name(name): read_snippet(snippets_dir, name, encoding=encoding)
        for name in list_snippets(snippets_dir)
    }
    snippets["base_user_data_sh"] = read_snippet(
        get_userdata_template_dir(), "base_user_data.sh", encoding=encoding
    )
    return snippets


def read_snippet(snippets_dir, name, encoding="utf-8"):
    """Read a snippet file.

    :rtype: `unicode`
    """
    return read_text_file(os.path.join(snippets_dir, name), encoding=encoding)


def is_snippet(filename):
    """Does `filename` represent a valid snippet name?"""
    return (
        not filename.startswith(".")
        and not filename.endswith(".pyc")
        and not filename.endswith("~")
        and filename != "__pycache__"
        and filename != "__init__.py"
        and filename != "tests"
    )


def list_snippets(snippets_dir):
    """List names of available snippets."""
    return list(filter(is_snippet, os.listdir(snippets_dir)))


def strip_name(snippet_name):
    """Canonicalize a snippet name."""
    # Dot suffixes do not work well in tempita variable names.
    return snippet_name.replace(".", "_")
