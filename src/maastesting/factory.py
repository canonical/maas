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

from functools import partial
import httplib
from itertools import (
    imap,
    islice,
    repeat,
    )
import random
import string


class Factory:

    random_letters = imap(
        random.choice, repeat(string.letters + string.digits))

    random_letters_with_spaces = imap(
        random.choice, repeat(string.letters + string.digits + ' '))

    random_http_responses = imap(
        random.choice, repeat(tuple(httplib.responses)))

    random_octet = partial(random.randint, 0, 255)

    random_octets = iter(random_octet, None)

    def getRandomString(self, size=10, spaces=False):
        if spaces:
            return "".join(islice(self.random_letters_with_spaces, size))
        else:
            return "".join(islice(self.random_letters, size))

    def getRandomEmail(self, login_size=10):
        return "%s@example.com" % self.getRandomString(size=login_size)

    def getRandomStatusCode(self):
        return next(self.random_http_responses)

    def getRandomBoolean(self):
        return random.choice((True, False))

    def getRandomPort(self, port_min=1024, port_max=65535):
        assert port_min >= 0 and port_max <= 65535
        return random.randint(port_min, port_max)

    def getRandomMACAddress(self):
        octets = islice(self.random_octets, 6)
        return b":".join(format(octet, b"02x") for octet in octets)


# Create factory singleton.
factory = Factory()
