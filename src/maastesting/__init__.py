# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""maastesting initialization."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    ]


# Nose is currently incompatible with testscenarios because of the assertions
# it makes about test names (see bug 872887 for details).
# Here we monkey patch node.ResultProxy.assertMyTest to turn it into
# a no-op.  Note that assertMyTest would already be a no-op if we were
# running python with -O.
def assertMyTest(self, test):
    pass


from nose.proxy import ResultProxy


ResultProxy.assertMyTest = assertMyTest
