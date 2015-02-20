# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The general handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "GeneralHandler",
    ]

from maasserver.node_action import ACTIONS_DICT
from maasserver.utils.osystems import (
    list_all_usable_osystems,
    list_all_usable_releases,
    )
from maasserver.websockets.base import Handler


class GeneralHandler(Handler):
    """Provides general methods that can be called from the client."""

    class Meta:
        allowed_methods = ['osinfo', 'actions']

    def osinfo(self):
        """Return all available operating systems and releases information."""
        return {
            "osystems": list_all_usable_releases(list_all_usable_osystems())
            }

    def actions(self):
        """Return all possible actions."""
        return [
            {
                "name": name,
                "title": action.display,
            }
            for name, action in ACTIONS_DICT.items()
            ]
