# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Set up test sessions against real Cobblers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'RealCobbler',
    ]

from os import environ
from textwrap import dedent
from urlparse import urlparse
from unittest import skipIf

from provisioningserver.cobblerclient import CobblerSession


class RealCobbler:
    """Factory for test sessions on a real Cobbler instance, if available.

    To enable tests, set the PSERV_TEST_COBBLER_URL environment variable to
    point to the real Cobbler instance you want to test against.  The URL
    should include username and password if required.

    Warning: this will mess with your Cobbler database.  Never do this with
    a production machine.
    """

    env_var = 'PSERV_TEST_COBBLER_URL'

    help_text_available = dedent("""\
        Set %s to the URL for a Cobbler instance to test against,
        e.g. http://username:password@example.com/cobbler_api.
        WARNING: this will modify your Cobbler database.
        """ % env_var)

    help_text_local = dedent("""\
        Set %s to the URL for a *local* Cobbler instance to test against,
        e.g. http://username:password@localhost/cobbler_api.
        WARNING: this will modify your Cobbler database.
        """ % env_var)

    def __init__(self):
        self.url = environ.get(self.env_var)
        if self.url is not None:
            urlparts = urlparse(self.url)
            self.username = urlparts.username or 'cobbler'
            self.password = urlparts.password or ''

    @property
    def is_available(self):
        """Is a real Cobbler available for tests?"""
        return self.url is not None

    @property
    def skip_unless_available(self):
        """Decorator to disable tests if no real Cobbler is available.

        Annotate tests like so::

          @real_cobbler.skip_unless_available
          def test_something_that_requires_a_real_cobbler(self):
              ...

        """
        return skipIf(not self.is_available, self.help_text_available)

    @property
    def is_local(self):
        """Is a real Cobbler installed locally available for tests?"""
        if self.is_available:
            hostname = urlparse(self.url).hostname
            return hostname == "localhost" or hostname.startswith("127.")
        else:
            return False

    @property
    def skip_unless_local(self):
        """Decorator to disable tests if no real *local* Cobbler is available.

        Annotate tests like so::

          @real_cobbler.skip_unless_local
          def test_something_that_requires_a_real_local_cobbler(self):
              ...

        """
        return skipIf(not self.is_local, self.help_text_local)

    def get_session(self):
        """Obtain a session on the real Cobbler.

        Returns None if no real Cobbler is available.
        """
        if self.is_available:
            return CobblerSession(self.url, self.username, self.password)
        else:
            return None
