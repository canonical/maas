# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS SSH Keys Import Action."""

import re

from maascli.api import Action
from maascli.command import CommandError


class SSHKeysImportAction(Action):
    """Provides custom logic to the sshkeys import action.

    Command: maas username sshkeys import

    The import command has the ability to upload the user's SSH Keys.
    """

    @staticmethod
    def name_value_pair(string):
        """Ensure that `string` is a valid ``name:value`` pair.

        When `string` is of the form ``lp:user-id`` or ``gh:user-id``,
        this returns a 2-tuple ``sshkeys, string``.
        """
        parts = re.split(r"(:)", string, 1)  # noqa: B034
        if len(parts) == 3 or string:
            return "keysource", string
        else:
            raise CommandError(
                "%r is not in a protocol:auth_id or auth_id format." % string
            )


# Each action sets this variable so the class can be picked up
# by get_action_class.
action_class = SSHKeysImportAction
