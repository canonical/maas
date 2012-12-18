# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate commissioning user-data from template and code snippets.

This combines the `user_data.template` and the snippets of code in the
`snippets` directory into the main commissioning script.

Its contents are not customizable.  To inject custom code, use the
:class:`CommissioningScript` model.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'generate_user_data',
    ]

from os import listdir
import os.path

import tempita


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
    return filter(is_snippet, listdir(snippets_dir))


def strip_name(snippet_name):
    """Canonicalize a snippet name."""
    # Dot suffixes do not work well in tempita variable names.
    return snippet_name.replace('.', '_')


def generate_user_data():
    """Produce the main commissioning script.

    The script was templated so that code snippets become easier to
    maintain, check for lint, and ideally, unit-test.  However its
    contents are static: there are no variables.  It's perfectly
    cacheable.

    :rtype: `bytes`
    """
    encoding = 'utf-8'
    commissioning_dir = os.path.dirname(__file__)
    template_file = os.path.join(commissioning_dir, 'user_data.template')
    snippets_dir = os.path.join(commissioning_dir, 'snippets')
    template = tempita.Template.from_filename(template_file, encoding=encoding)

    snippets = {
        strip_name(name): read_snippet(snippets_dir, name, encoding=encoding)
        for name in list_snippets(snippets_dir)
    }
    return template.substitute(snippets).encode('utf-8')
