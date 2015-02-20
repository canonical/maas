# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.general`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.node_action import ACTIONS_DICT
from maasserver.testing.factory import factory
from maasserver.testing.osystems import make_osystem_with_releases
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.general import GeneralHandler


class TestGeneralHandler(MAASServerTestCase):

    def test_osinfo(self):
        handler = GeneralHandler(factory.make_User())
        info = make_osystem_with_releases(self)
        osinfo_expected = {
            "osystems": {
                info['name']: [
                    "%s/%s" % (info['name'], release['name'])
                    for release in info['releases']
                    ],
                },
            }
        self.assertItemsEqual(osinfo_expected, handler.osinfo())

    def test_actions(self):
        handler = GeneralHandler(factory.make_User())
        actions_expected = [
            {
                "name": name,
                "title": action.display,
            }
            for name, action in ACTIONS_DICT.items()
            ]
        self.assertItemsEqual(actions_expected, handler.actions())
