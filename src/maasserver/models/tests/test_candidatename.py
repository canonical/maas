# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test :py:class:`maasserver.models.candidatename.CandidateName` et al."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models.candidatename import gen_candidate_names
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    AllMatch,
    MatchesRegex,
)


class TestGenCandidateName(MAASServerTestCase):

    def test__generates_names_containing_two_words(self):
        # Testing all candidate names, even all 1.2 million of them, is
        # reasonable: it only takes ~2 seconds.
        self.assertThat(
            gen_candidate_names(),
            AllMatch(MatchesRegex('^[a-z]+-[a-z]+$')))
