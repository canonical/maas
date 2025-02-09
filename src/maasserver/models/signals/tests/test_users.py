# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of user signals."""

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestUserUsername(MAASServerTestCase):
    """Test that event's `username` is set when the user is
    going to be deleted."""

    def test_deleting_user_updates_event_username(self):
        user = factory.make_admin()
        username = user.username
        events = [factory.make_Event(user=user) for _ in range(3)]
        user.delete()
        for event in events:
            self.assertEqual(event.username, username)
