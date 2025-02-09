# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the documentation of defined commands.

Specifically, check
:py:class:`~twisted.protocols.amp.Command` subclasses in the
MAAS codebase.
"""

from inspect import getdoc
from itertools import chain

from twisted.protocols import amp

from maastesting.testcase import MAASTestCase
import provisioningserver.rpc.cluster
import provisioningserver.rpc.common
import provisioningserver.rpc.region


def get_commands(module):
    """Return command classes from the given module."""
    for name, value in vars(module).items():  # noqa: B007
        if isinstance(value, type):
            if issubclass(value, amp.Command):
                yield value


class TestDocs(MAASTestCase):
    scenarios = sorted(
        (command.__name__, {"command": command})
        for command in chain(
            get_commands(provisioningserver.rpc.common),
            get_commands(provisioningserver.rpc.cluster),
            get_commands(provisioningserver.rpc.region),
        )
    )

    since_clause_missing_message = (
        "Command class does not have a :since: clause. The version in "
        "which this command will be (or already has been) introduced "
        "must be recorded, 1.6 for example."
    )

    since_clause_version_not_recognised = (
        "Command's :since: clause does not contain a recognised version, "
        "1.6 for example."
    )

    def test_since_clause(self):
        doc = getdoc(self.command)
        self.assertIn(":since", doc, self.since_clause_missing_message)
        self.assertRegex(
            doc,
            "(?sm).*^:since: *[1-9][.][0-9]+([.][0-9]+)?$",
            self.since_clause_version_not_recognised,
        )
