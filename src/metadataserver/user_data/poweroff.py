# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Poweroff userdata generation."""

__all__ = [
    "generate_user_data",
]

from metadataserver.user_data.snippets import get_userdata_template_dir
from metadataserver.user_data.utils import (
    generate_user_data as _generate_user_data,
)


def generate_user_data(node):
    """Produce the poweroff script.

    :rtype: `bytes`
    """
    userdata_dir = get_userdata_template_dir()
    result = _generate_user_data(
        node, userdata_dir, 'user_data_poweroff.template',
        'user_data_config.template')
    return result
