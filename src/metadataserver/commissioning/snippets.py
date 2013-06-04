# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Low-level routines for access to snippets.

These are used by the user-data code, but also by `setup.py`.  That's why
importing this must not pull in any unnecessary framework modules etc.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'list_snippets',
    'read_snippet',
    'strip_name',
    ]

import os


def read_snippet(snippets_dir, name, encoding='utf-8'):
    """Read a snippet file.

    :rtype: `unicode`
    """
    path = os.path.join(snippets_dir, name)
    with open(path, 'rb') as snippet_file:
        return snippet_file.read().decode(encoding)


def is_snippet(filename):
    """Does `filename` represent a valid snippet name?"""
    return all([
        not filename.startswith('.'),
        filename != '__init__.py',
        not filename.endswith('.pyc'),
        not filename.endswith('~'),
        ])


def list_snippets(snippets_dir):
    """List names of available snippets."""
    return filter(is_snippet, os.listdir(snippets_dir))


def strip_name(snippet_name):
    """Canonicalize a snippet name."""
    # Dot suffixes do not work well in tempita variable names.
    return snippet_name.replace('.', '_')
