# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to Curtin."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'compose_mv_command',
    'compose_recursive_copy',
    'compose_write_text_file',
    ]


def compose_write_text_file(path, content, owner='root:root',
                            permissions=0600):
    """Return preseed for uploading a text file to the install target.

    Use this to write files into the filesystem that Curtin is installing.  The
    result goes into a `write_files` preseed entry.
    """
    return {
        'path': path,
        'content': content,
        'owner': owner,
        'permissions': '0%o' % permissions,
        }


def compose_mv_command(source, dest):
    """Return preseed for running the `mv` command in the install target.

    Use this for moving files around in the filesystem that Curtin is
    installing.  The result goes in a preseed entry for running commands, such
    as an entry in `late_commands` dict.
    """
    return [
        'curtin', 'in-target', '--',
        'mv', '--', source, dest,
        ]


def compose_recursive_copy(source, dest):
    """Return preseed for running a recursive `cp` in the install target."""
    return [
        'curtin', 'in-target', '--',
        'cp', '-r', '-p', '--', source, dest,
        ]
