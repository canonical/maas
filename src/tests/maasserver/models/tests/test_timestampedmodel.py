# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Gap-free tests for `maasserver.models.timestampedmodel`, split out of the
legacy `src/maasserver/models/tests/test_timestampedmodel.py`: the legacy
`TestTimestampedModel` class stays there under nose (idea 002), while this
class runs under pytest."""

from datetime import datetime

from maasserver.models.timestampedmodel import now
from maasserver.testing.testcase import MAASServerTestCase


class TestUtilities(MAASServerTestCase):
    def test_now_returns_datetime(self):
        self.assertIsInstance(now(), datetime)
