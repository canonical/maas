# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `sampledata` module."""

__all__ = []

from maasserver.testing import sampledata
from maasserver.testing.testcase import MAASServerTestCase


class TestPopulates(MAASServerTestCase):
    """Tests for `sampledata.populate`."""

    def test_runs(self):
        sampledata.populate()
