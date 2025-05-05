# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for the system user that represents node-group workers."""

from django.contrib.auth.models import User

from maascommon.constants import MAAS_USER_USERNAME
from maasserver.models import UserProfile
from maasserver.models.user import SYSTEM_USERS
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.worker_user import get_worker_user


class TestNodeGroupUser(MAASServerTestCase):
    """Test the special "user" that workers use to access the API."""

    def test_get_worker_user_always_returns_same_user(self):
        self.assertEqual(get_worker_user().id, get_worker_user().id)

    def test_get_worker_user_holds_the_worker_user(self):
        worker_user = get_worker_user()
        self.assertIsInstance(worker_user, User)
        self.assertEqual(MAAS_USER_USERNAME, worker_user.username)

    def test_worker_user_is_system_user(self):
        worker_user = get_worker_user()
        self.assertIn(worker_user.username, SYSTEM_USERS)
        profile = None
        try:
            profile = worker_user.userprofile
        except UserProfile.DoesNotExist:
            # Expected.
            pass
        self.assertIsNone(profile)
