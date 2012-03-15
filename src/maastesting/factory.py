# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test object factories."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "factory",
    ]

import httplib
import random
import string


class Factory:

    def getRandomString(self, size=10):
        return "".join(
            random.choice(string.letters + string.digits)
            for x in range(size))

    def getRandomEmail(self, login_size=10):
        return "%s@example.com" % self.getRandomString(size=login_size)

    def getRandomStatusCode(self):
        return random.choice(list(httplib.responses))

    def getRandomBoolean(self):
        return random.choice((True, False))


# Create factory singleton.
factory = Factory()
