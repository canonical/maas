# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test object factories."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "factory",
    "NO_VALUE",
    ]

import datetime
from functools import partial
import httplib
from itertools import (
    imap,
    islice,
    repeat,
    )
import os
import os.path
import random
import string
import subprocess
import time
from uuid import uuid1

from maastesting.fixtures import TempDirectory
from netaddr import (
    IPAddress,
    IPNetwork,
    )

# Occasionally a parameter needs separate values for None and "no value
# given, make one up."  In that case, use NO_VALUE as the default and
# accept None as a normal value.
NO_VALUE = object()


class Factory:

    random_letters = imap(
        random.choice, repeat(string.letters + string.digits))

    random_letters_with_spaces = imap(
        random.choice, repeat(string.letters + string.digits + ' '))

    # See django.contrib.auth.forms.UserCreationForm.username.
    random_letters_for_usernames = imap(
        random.choice, repeat(string.letters + '.@+-'))

    random_http_responses = imap(
        random.choice, repeat(tuple(httplib.responses)))

    random_octet = partial(random.randint, 0, 255)

    random_octets = iter(random_octet, None)

    def getRandomString(self, size=10, spaces=False):
        if spaces:
            return "".join(islice(self.random_letters_with_spaces, size))
        else:
            return "".join(islice(self.random_letters, size))

    def getRandomBytes(self, size=10):
        return os.urandom(size)

    def getRandomUsername(self, size=10):
        return "".join(islice(self.random_letters_for_usernames, size))

    def getRandomEmail(self, login_size=10):
        return "%s@example.com" % self.getRandomString(size=login_size)

    def getRandomStatusCode(self):
        return next(self.random_http_responses)

    def getRandomBoolean(self):
        return random.choice((True, False))

    def getRandomPort(self, port_min=1024, port_max=65535):
        assert port_min >= 0 and port_max <= 65535
        return random.randint(port_min, port_max)

    def getRandomIPAddress(self):
        octets = islice(self.random_octets, 4)
        return '%d.%d.%d.%d' % tuple(octets)

    def getRandomUUID(self):
        return unicode(uuid1())

    def getRandomNetwork(self, slash=None):
        ip = self.getRandomIPAddress()
        if slash is None:
            # Create a *small* network.
            slash = random.randint(24, 30)
        return IPNetwork('%s/%s' % (ip, slash))

    def getRandomIPInNetwork(self, network):
        return bytes(IPAddress(
            random.randint(network.first, network.last)))

    def getRandomMACAddress(self, delimiter=":"):
        assert isinstance(delimiter, unicode)
        octets = islice(self.random_octets, 6)
        return delimiter.join(format(octet, "02x") for octet in octets)

    def make_random_leases(self, num_leases=1):
        """Create a dict of arbitrary ip-to-mac address mappings."""
        # This could be a dict comprehension, but the current loop
        # guards against shortfalls as random IP addresses collide.
        leases = {}
        while len(leases) < num_leases:
            leases[self.getRandomIPAddress()] = self.getRandomMACAddress()
        return leases

    def getRandomDate(self, year=2011):
        start = time.mktime(datetime.datetime(year, 1, 1).timetuple())
        end = time.mktime(datetime.datetime(year + 1, 1, 1).timetuple())
        stamp = random.randrange(start, end)
        return datetime.datetime.fromtimestamp(stamp)

    def make_file(self, location, name=None, contents=None):
        """Create a file, and write data to it.

        Prefer the eponymous convenience wrapper in
        :class:`maastesting.testcase.MAASTestCase`.  It creates a temporary
        directory and arranges for its eventual cleanup.

        :param location: Directory.  Use a temporary directory for this, and
            make sure it gets cleaned up after the test!
        :param name: Optional name for the file.  If none is given, one will
            be made up.
        :param contents: Optional contents for the file.  If omitted, some
            arbitrary ASCII text will be written.
        :type contents: unicode, but containing only ASCII characters.
        :return: Path to the file.
        """
        if name is None:
            name = self.getRandomString()
        if contents is None:
            contents = self.getRandomString().encode('ascii')
        path = os.path.join(location, name)
        with open(path, 'w') as f:
            f.write(contents)
        return path

    def make_name(self, prefix=None, sep='-', size=6):
        """Generate a random name.

        :param prefix: Optional prefix.  Pass one to help make test failures
            and tracebacks easier to read!  If you don't, you might as well
            use `getRandomString`.
        :param sep: Separator that will go between the prefix and the random
            portion of the name.  Defaults to a dash.
        :param size: Length of the random portion of the name.  Don't get
            hung up on this; you may need more if uniqueness is really
            important or less if it doesn't but legibility does, but
            generally, use the default.
        :return: A randomized unicode string.
        """
        return sep.join(
            filter(None, [prefix, self.getRandomString(size=size)]))

    def make_hostname(self, prefix='host', *args, **kwargs):
        """Generate a random hostname.

        The returned hostname is lowercase because python's urlparse
        implicitely lowercases the hostnames."""
        return self.make_name(prefix=prefix, *args, **kwargs).lower()

    def make_names(self, *prefixes):
        """Generate random names.

        Yields a name for each prefix specified.

        :param prefixes: Zero or more prefixes. See `make_name`.
        """
        for prefix in prefixes:
            yield self.make_name(prefix)

    def make_tarball(self, location, contents):
        """Create a tarball containing the given files.

        :param location: Path to a directory where the tarball can be stored.
        :param contents: A dict mapping file names to file contents.  Where
            the value is `None`, the file will contain arbitrary data.
        :return: Path to a gzip-compressed tarball.
        """
        tarball = os.path.join(location, '%s.tar.gz' % self.make_name())
        with TempDirectory() as working_dir:
            source = working_dir.path
            for name, content in contents.iteritems():
                self.make_file(source, name, content)

            subprocess.check_call(['tar', '-C', source, '-czf', tarball, '.'])

        return tarball


# Create factory singleton.
factory = Factory()
