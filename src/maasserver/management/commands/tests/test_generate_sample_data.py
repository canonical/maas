# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the `generate_sample_data` management command."""


from django.core.management import call_command
from testtools.matchers import Equals, MatchesRegex

from maasserver.testing import sampledata
from maastesting.fixtures import CaptureStandardIO, ImportErrorFixture
from maastesting.matchers import MockCalledOnceWith, MockNotCalled
from maastesting.testcase import MAASTestCase


class TestGenerateSampleData(MAASTestCase):
    def test_exists_and_calls_populate(self):
        self.patch(sampledata, "populate")
        call_command("generate_sample_data")
        self.assertThat(sampledata.populate, MockCalledOnceWith())

    def test_not_available_in_production(self):
        self.useFixture(ImportErrorFixture("maasserver.testing", "sampledata"))
        self.patch(sampledata, "populate")
        with CaptureStandardIO() as stdio:
            self.assertRaises(SystemExit, call_command, "generate_sample_data")
        self.assertThat(sampledata.populate, MockNotCalled())
        self.assertThat(stdio.getOutput(), Equals(""))
        self.assertThat(
            stdio.getError(),
            MatchesRegex(
                "Sample data generation is available only in development "
                "and test environments.\n\\s*"
            ),
        )
