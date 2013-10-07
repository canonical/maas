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

str = None

__metaclass__ = type
__all__ = [
    'list_snippets',
    'read_snippet',
    'strip_name',
    'get_snippet_context',
    'get_userdata_template_dir',
    ]

import os

from provisioningserver.utils import (
    locate_config,
    read_text_file,
    )


USERDATA_BASE_DIR = 'templates/commissioning-user-data'


def get_userdata_template_dir():
    """Return the absolute location of the userdata
    template directory."""
    return locate_config(USERDATA_BASE_DIR)


def get_snippet_context(snippets_dir=None, encoding='utf-8'):
    """Return the context of all of the snippets."""
    if snippets_dir is None:
        snippets_dir = os.path.join(get_userdata_template_dir(), 'snippets')
    snippets = {
        strip_name(name): read_snippet(snippets_dir, name, encoding=encoding)
        for name in list_snippets(snippets_dir)
        }
    return snippets


def read_snippet(snippets_dir, name, encoding='utf-8'):
    """Read a snippet file.

    :rtype: `unicode`
    """
    return read_text_file(os.path.join(snippets_dir, name), encoding=encoding)


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
