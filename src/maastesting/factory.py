# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test object factories."""


import datetime
from enum import Enum
from functools import partial
import http.client
import io
from itertools import combinations, count, islice, repeat
import os
import os.path
import random
import string
import subprocess
import time
import unicodedata
from unittest import mock
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID, uuid1

from distro_info import UbuntuDistroInfo
from netaddr import IPAddress, IPNetwork, IPSet

from maastesting.fixtures import TempDirectory

# Occasionally a parameter needs separate values for None and "no value
# given, make one up."  In that case, use NO_VALUE as the default and
# accept None as a normal value.
NO_VALUE = object()


EMPTY_SET = frozenset()


class TooManyRandomRetries(Exception):
    """Something that relies on luck did not get lucky.

    Some factory methods need to generate random items until they find one
    that meets certain requirements.  This exception indicates that it took
    too many retries, which may mean that no matching item is possible.
    """


def network_clashes(network, other_networks):
    """Does the IP range for `network` clash with any in `other_networks`?

    :param network: An `IPNetwork`.
    :param other_networks: An iterable of `IPNetwork` items.
    :return: Whether the IP range for `network` overlaps with any of those
        for the networks in `other_networks`.
    """
    for other_network in other_networks:
        if network in other_network or other_network in network:
            return True
    return False


class Factory:

    random_letters = map(
        random.choice, repeat(string.ascii_letters + string.digits)
    )

    random_letters_with_spaces = map(
        random.choice, repeat(string.ascii_letters + string.digits + " ")
    )

    # See django.contrib.auth.forms.UserCreationForm.username.
    random_letters_for_usernames = map(
        random.choice, repeat(string.ascii_letters + ".@+-")
    )

    random_http_responses = map(
        random.choice, repeat(tuple(http.client.responses))
    )

    random_octet = partial(random.randint, 0, 255)

    random_octets = iter(random_octet, None)

    random_unicode_codepoint = partial(random.randint, 0, 0x10FFFF)

    random_unicode_codepoints = iter(random_unicode_codepoint, None)

    random_unicode_characters = (
        char
        for char in map(chr, random_unicode_codepoints)
        if unicodedata.category(char)[0] in "LMNPS"
    )

    random_unicode_non_ascii_characters = (
        char for char in random_unicode_characters if ord(char) >= 128
    )

    random_unicode_characters_with_spaces = (
        char
        for char in map(chr, random_unicode_codepoints)
        if unicodedata.category(char)[0] in "LMNPSZ"
    )

    random_unicode_non_ascii_characters_with_spaces = (
        char
        for char in random_unicode_characters_with_spaces
        if char == " " or ord(char) >= 128
    )

    def make_string(self, size=10, spaces=False, prefix=""):
        """Return a `str` filled with random ASCII letters or digits."""
        source = (
            self.random_letters_with_spaces if spaces else self.random_letters
        )
        return prefix + "".join(islice(source, size))

    def make_hex_string(self, size=4):
        return "".join(
            [random.choice(string.hexdigits) for _ in range(0, size)]
        )

    def make_unicode_string(self, size=10, spaces=False, prefix=""):
        """Return a `str` filled with random Unicode characters."""
        source = (
            self.random_unicode_characters_with_spaces
            if spaces
            else self.random_unicode_characters
        )
        return prefix + "".join(islice(source, size))

    def make_unicode_non_ascii_string(self, size=10, spaces=False, prefix=""):
        """Return a `str` filled with random non-ASCII Unicode characters."""
        source = (
            self.random_unicode_non_ascii_characters_with_spaces
            if spaces
            else self.random_unicode_non_ascii_characters
        )
        return prefix + "".join(islice(source, size))

    def make_bytes(self, size=10):
        """Return a `bytes` filled with random data."""
        return os.urandom(size)

    def make_username(self, size=10):
        """Create an arbitrary user name (but not the actual user)."""
        return "".join(islice(self.random_letters_for_usernames, size))

    def make_email_address(self, login_size=10):
        """Generate an arbitrary email address."""
        return "%s@example.com" % self.make_string(size=login_size)

    def make_status_code(self):
        """Return an arbitrary HTTP status code."""
        return next(self.random_http_responses)

    exception_type_names = ("TestException#%d" % i for i in count(1))

    def make_exception_type(self, bases=(Exception,), **namespace):
        return type(next(self.exception_type_names), bases, namespace)

    def make_exception(self, message=None, bases=(Exception,), **namespace):
        exc_type = self.make_exception_type(bases, **namespace)
        return exc_type() if message is None else exc_type(message)

    def make_absolute_path(
        self, directories=3, directory_length=10, path_seperator="/"
    ):
        return path_seperator + path_seperator.join(
            self.make_string(size=directory_length) for _ in range(directories)
        )

    def pick_bool(self):
        """Return an arbitrary Boolean value (`True` or `False`)."""
        return random.choice((True, False))

    def pick_enum(self, enum, *, but_not=EMPTY_SET):
        """Pick a random item from an enumeration class.

        :param enum: An enumeration class such as `NODE_STATUS`. Can also be
            an `enum.Enum` subclass.
        :return: The value of one of its items.
        :param but_not: A list of choices' IDs to exclude.
        :type but_not: Sequence.
        """
        if issubclass(enum, Enum):
            return random.choice(
                [value for value in enum if value not in but_not]
            )
        else:
            return random.choice(
                [
                    value
                    for key, value in vars(enum).items()
                    if not key.startswith("_") and value not in but_not
                ]
            )

    def pick_port(self, port_min=1024, port_max=65535):
        assert port_min >= 0 and port_max <= 65535
        return random.randint(port_min, port_max)

    def pick_choice(self, choices, but_not=None):
        """Pick a random item from `choices`.

        :param choices: A sequence of choices in Django form choices format:
            [
                ('choice_id_1', "Choice name 1"),
                ('choice_id_2', "Choice name 2"),
            ]
        :param but_not: A list of choices' IDs to exclude.
        :type but_not: Sequence.
        :return: The "id" portion of a random choice out of `choices`.
        """
        if but_not is None:
            but_not = ()
        return random.choice(
            [choice for choice in choices if choice[0] not in but_not]
        )[0]

    def make_vlan_tag(self, allow_none=False, *, but_not=EMPTY_SET):
        """Create a random VLAN tag.

        :param allow_none: Whether `None` ("no VLAN") can be allowed as an
            outcome.  If `True`, `None` will be included in the possible
            results with a deliberately over-represented probability, in order
            to help trip up bugs that might only show up once in about 4094
            calls otherwise.
        :param but_not: A set of tags that should not be returned.  Any zero
            or `None` entries will be ignored.
        """
        if allow_none and self.pick_bool():
            return None
        else:
            for _ in range(100):
                vlan_tag = random.randint(1, 0xFFE)
                if vlan_tag not in but_not:
                    return vlan_tag
            raise TooManyRandomRetries("Could not find an available VLAN tag.")

    def ip_to_url_format(self, ip):
        # We return either '[ip:v6:address]' or 'a.b.c.d' depending on the
        # family of the IP Address.
        ip_addr = IPAddress(ip)
        if ip_addr.version == 6:
            return "[%s]" % str(ip_addr)
        else:
            return "%s" % str(ip_addr)

    def make_ipv4_address(self):
        octets = list(islice(self.random_octets, 4))
        if octets[0] == 0:
            octets[0] = 1
        return "%d.%d.%d.%d" % tuple(octets)

    def make_ipv6_address(self):
        # We return from the fc00::/7 space because that's a private
        # space and shouldn't cause problems of addressing the outside
        # world.
        network = IPNetwork("fc00::/7")
        # We can't use random.choice() because there are too many
        # elements in network.
        random_address_index = random.randint(0, network.size - 1)
        return str(IPAddress(network[random_address_index]))

    def make_ip_address(self, ipv6=None):
        """Create a random ip address.

        :param ipv6: True for ipv6, False for ipv4, None for random.

        :return: an IP Address
        :rtype: string
        """
        if ipv6 is None:
            ipv6 = random.randint(0, 1)
        # intentionally allowing all "true" values, including "1".
        if ipv6:
            return self.make_ipv6_address()
        else:
            return self.make_ipv4_address()

    def make_UUID(self):
        return str(uuid1())

    def make_UUID_with_timestamp(self, timestamp, clock_seq=None, node=None):
        if node is None:
            node = random.getrandbits(48) | 0x010000000000
        if clock_seq is None:
            clock_seq = random.getrandbits(14)
        timestamp = int(timestamp * 1e9 / 100) + 0x01B21DD213814000
        time_low = timestamp & 0xFFFFFFFF
        time_mid = (timestamp >> 32) & 0xFFFF
        time_hi_version = (timestamp >> 48) & 0x0FFF
        clock_seq_low = clock_seq & 0xFF
        clock_seq_hi_variant = (clock_seq >> 8) & 0x3F
        fields = (
            time_low,
            time_mid,
            time_hi_version,
            clock_seq_hi_variant,
            clock_seq_low,
            node,
        )
        return str(UUID(fields=fields, version=1))

    def _make_random_network(
        self,
        slash=None,
        but_not=EMPTY_SET,
        disjoint_from=None,
        random_address_factory=None,
    ):
        """Generate a random IP network.

        :param slash: Netmask or bit width of the network, e.g. 24 or
            '255.255.255.0' for what used to be known as a class-C network.
        :param but_not: Optional iterable of `IPNetwork` objects whose values
            should not be returned.  Use this when you need a different network
            from any returned previously.  The new network may overlap any of
            these, but it won't be identical.
        :param disjoint_from: Optional iterable of `IPNetwork` objects whose
            IP ranges the new network must not overlap.
        :param random_address_factory: A callable that returns a random IP
            address. If not provided, will default to
            Factory.make_ipv4_address().
        :return: A network spanning at least 8 IP addresses (at most 29 bits).
        :rtype: :class:`IPNetwork`
        """
        if disjoint_from is None:
            disjoint_from = []
        if slash is None:
            slash = random.randint(16, 29)
        if random_address_factory is None:
            random_address_factory = self.make_ipv4_address
        # Look randomly for a network that matches our criteria.
        for _ in range(100):
            network = IPNetwork(f"{random_address_factory()}/{slash}").cidr
            forbidden = False
            for excluded_network in but_not:
                if excluded_network == network:
                    forbidden = True
                    break
            clashes = network_clashes(network, disjoint_from)
            if not forbidden and not clashes:
                return network
        raise TooManyRandomRetries("Could not find available network")

    def make_ipv4_network(
        self, slash=None, *, but_not=EMPTY_SET, disjoint_from=None
    ):
        """Generate a random IPv4 network.

        :param slash: Netmask or bit width of the network, e.g. 24 or
            '255.255.255.0' for what used to be known as a class-C network.
        :param but_not: Optional iterable of `IPNetwork` objects whose values
            should not be returned.  Use this when you need a different network
            from any returned previously.  The new network may overlap any of
            these, but it won't be identical.
        :param disjoint_from: Optional iterable of `IPNetwork` objects whose
            IP ranges the new network must not overlap.
        :return: A network spanning at least 14 host addresses (at most 28 bits).
        :rtype: :class:`IPNetwork`
        """
        if slash is None:
            slash = random.randint(24, 28)
        return self._make_random_network(
            slash=slash,
            but_not=but_not,
            disjoint_from=disjoint_from,
            random_address_factory=self.make_ipv4_address,
        )

    def make_ipv6_network(
        self, slash=None, *, but_not=EMPTY_SET, disjoint_from=None
    ):
        """Generate a random IPv6 network.

        :param slash: Netmask or bit width of the network. If not
            specified, will default to a bit width of between 48 and 64
        :param but_not: Optional iterable of `IPNetwork` objects whose values
            should not be returned.  Use this when you need a different network
            from any returned previously.  The new network may overlap any of
            these, but it won't be identical.
        :param disjoint_from: Optional iterable of `IPNetwork` objects whose
            IP ranges the new network must not overlap.
        :return: A network spanning at least 8 IP addresses.
        :rtype: :class:`IPNetwork`
        """
        if slash is None:
            slash = random.randint(48, 64)
        return self._make_random_network(
            slash=slash,
            but_not=but_not,
            disjoint_from=disjoint_from,
            random_address_factory=self.make_ipv6_address,
        )

    def make_ip4_or_6_network(
        self, version=None, host_bits=None, but_not=EMPTY_SET
    ):
        """Generate a random IPv4 or IPv6 network."""
        slash = None
        if version is None:
            version = random.choice([4, 6])
        if version == 4:
            if host_bits is not None:
                slash = 32 - host_bits
            return self.make_ipv4_network(slash=slash, but_not=but_not)
        else:
            if host_bits is not None:
                slash = 128 - host_bits
            return self.make_ipv6_network(slash=slash, but_not=but_not)

    def pick_ip_in_dynamic_range(self, ngi, *, but_not=EMPTY_SET):
        first = ngi.get_dynamic_ip_range().first
        last = ngi.get_dynamic_ip_range().last
        but_not = {IPAddress(but) for but in but_not if but is not None}
        for _ in range(100):
            address = IPAddress(random.randint(first, last))
            if address not in but_not:
                return str(address)
        raise TooManyRandomRetries(
            "Could not find available IP in static range"
        )

    def pick_ip_in_static_range(self, ngi, *, but_not=EMPTY_SET):
        first = ngi.get_static_ip_range().first
        last = ngi.get_static_ip_range().last
        but_not = {IPAddress(but) for but in but_not if but is not None}
        for _ in range(100):
            address = IPAddress(random.randint(first, last))
            if address not in but_not:
                return str(address)
        raise TooManyRandomRetries(
            "Could not find available IP in static range"
        )

    def pick_ip_in_network(self, network, *, but_not=EMPTY_SET):
        excluded_set = IPSet()
        for exclusion in but_not:
            if isinstance(exclusion, str):
                exclusion = IPAddress(exclusion)
            excluded_set.add(exclusion)
        # Unless the prefix length is very small, make sure we don't select
        # a normally-unusable IP address.
        if network.version == 6 and network.prefixlen < 127:
            # Don't pick the all-zeroes address, since it has special meaning
            # in IPv6 as the subnet-router anycast address. IPv6 does not have
            # a broadcast address, though.
            first, last = network.first + 1, network.last
            network_size = network.size - 1
        elif network.prefixlen < 31:
            # Don't pick broadcast or network addresses.
            first, last = network.first + 1, network.last - 1
            network_size = network.size - 2
        else:
            first, last = network.first, network.last
            network_size = network.size
        if len(but_not) == network_size:
            raise ValueError(
                "No IP addresses available in network: %s (but_not=%r)"
                % (network, but_not)
            )
        for _ in range(100):
            address = IPAddress(random.randint(first, last))
            if address not in excluded_set:
                return str(address)
        raise TooManyRandomRetries(
            "Could not find available IP in network: %s (but_not=%r)"
            % (network, but_not)
        )

    def make_ip_range(self, network):
        """Return a pair of IP addresses from the given network.

        :param network: Return IP addresses within this network.
        :return: A pair of `IPAddress`.
        """
        for _ in range(100):
            ip_range = tuple(
                sorted(
                    IPAddress(factory.pick_ip_in_network(network))
                    for _ in range(2)
                )
            )
            if ip_range[0] < ip_range[1]:
                return ip_range
        raise TooManyRandomRetries(
            "Could not find available IP range in network: %s" % network
        )

    def make_ipv4_range(self, network=None):
        """Return a pair of IPv4 addresses.

        :param network: Return IP addresses within this network.
        :return: A pair of `IPAddress`.
        """
        if network is None:
            network = self.make_ipv4_network()
        return self.make_ip_range(network=network)

    def make_ipv6_range(self, network=None):
        """Return a pair of IPv6 addresses.

        :param network: Return IP addresses within this network.
        :return: A pair of `IPAddress`.
        """
        if network is None:
            network = self.make_ipv6_network()
        return self.make_ip_range(network=network)

    def make_mac_address(self, delimiter=":", padding=True):
        assert isinstance(delimiter, str)
        octets = islice(self.random_octets, 6)
        return delimiter.join(
            format(octet, "02x" if padding else "x") for octet in octets
        )

    def make_random_leases(self, num_leases=1):
        """Create a dict of arbitrary ip-to-mac address mappings."""
        # This could be a dict comprehension, but the current loop
        # guards against shortfalls as random IP addresses collide.
        leases = {}
        while len(leases) < num_leases:
            leases[self.make_ipv4_address()] = self.make_mac_address()
        return leases

    def make_date(self, year=2017):
        start = time.mktime(datetime.datetime(year, 1, 1).timetuple())
        end = time.mktime(datetime.datetime(year + 1, 1, 1).timetuple())
        stamp = random.uniform(start, end)
        return datetime.datetime.fromtimestamp(stamp)

    def make_timedelta(self):
        return datetime.timedelta(
            days=random.randint(0, 3 * 365),
            seconds=random.randint(0, 24 * 60 * 60 - 1),
            microseconds=random.randint(0, 999999),
        )

    def make_file(self, location, name=None, contents=None):
        """Create a file, and write data to it.

        Prefer the eponymous convenience wrapper in
        :class:`maastesting.testcase.MAASTestCase`.  It creates a temporary
        directory and arranges for its eventual cleanup.

        :param location: Directory.  Use a temporary directory for this, and
            make sure it gets cleaned up after the test!
        :param name: Optional name for the file.  If none is given, one will
            be made up.
        :param contents: Optional contents for the file. If omitted, some
            arbitrary ASCII text will be written. If Unicode content is
            provided, it will be encoded with UTF-8.
        :type contents: unicode, but containing only ASCII characters.
        :return: Path to the file.
        """
        if name is None:
            name = self.make_string()
        if contents is None:
            contents = self.make_string().encode("ascii")
        if isinstance(contents, str):
            contents = contents.encode("utf-8")
        path = os.path.join(location, name)
        with open(path, "wb") as f:
            f.write(contents)
        return path

    def make_name(self, prefix=None, sep="-", size=6):
        """Generate a random name.

        :param prefix: Optional prefix.  Pass one to help make test failures
            and tracebacks easier to read!  If you don't, you might as well
            use `make_string`.
        :param sep: Separator that will go between the prefix and the random
            portion of the name.  Defaults to a dash.
        :param size: Length of the random portion of the name.  Don't get
            hung up on this; you may need more if uniqueness is really
            important or less if it doesn't but legibility does, but
            generally, use the default.
        :return: A randomized unicode string.
        """
        if prefix is None:
            return self.make_string(size=size)
        else:
            return prefix + sep + self.make_string(size=size)

    def make_name_avoiding_collision(
        self, other, prefix=None, sep="-", size=6, min_substr_len=2
    ):
        """Generate a random name that does not contain any of the substrings
        of `other` of a defined minimum length.

        :param other: The other name to check against.
        :param prefix: Optional prefix.  Pass one to help make test failures
            and tracebacks easier to read!  If you don't, you might as well
            use `make_string`.
        :param sep: Separator that will go between the prefix and the random
            portion of the name.  Defaults to a dash.
        :param size: Length of the random portion of the name.  Don't get
            hung up on this; you may need more if uniqueness is really
            important or less if it doesn't but legibility does, but
            generally, use the default.
        :param min_substr_len: Length of the substrings of `other` to match
            against. Defaults to 2.
        :return: A randomized unicode string.
        """

        def _collision(name):
            substrs = ["".join(x) for x in combinations(other, min_substr_len)]
            if any(substr in name for substr in substrs):
                return True

        name = self.make_name(prefix=prefix, sep=sep, size=size)
        while _collision(name):
            name = self.make_name(prefix=prefix, sep=sep, size=size)
        return name

    def make_hostname(self, prefix="host", *args, **kwargs):
        """Generate a random hostname.

        The returned hostname is lowercase because python's urlparse
        implicitely lowercases the hostnames."""
        return self.make_name(prefix=prefix, *args, **kwargs).lower()

    # Always select from a scheme that allows parameters in the URL so
    # that we can round-trip a URL with params successfully (otherwise
    # the params don't get parsed out of the path).
    _make_parsed_url_schemes = tuple(
        scheme for scheme in urllib.parse.uses_params if scheme != ""
    )

    def make_parsed_url(
        self,
        scheme=None,
        netloc=None,
        path=None,
        port=None,
        params=None,
        query=None,
        fragment=None,
    ):
        """Generate a random parsed URL object.

        Contains randomly generated values for all parts of a URL: scheme,
        location, path, parameters, query, and fragment. However, each part
        can be overridden individually.

        If port=None or port=True, make_port() will be used to select a random
        port, while port=False will create a netloc for the URL that does not
        specify a port. To specify a port in netloc, port parameter
        must be False.

        :return: Instance of :py:class:`urlparse.ParseResult`.
        """
        if port is not False and netloc is not None and netloc.count(":") == 1:
            raise AssertionError(
                "A port number has been requested, however the given netloc "
                "spec %r already contains a port number." % (netloc,)
            )
        if scheme is None:
            # Select a scheme that allows parameters; see above.
            scheme = random.choice(self._make_parsed_url_schemes)
        if port is None or port is True:
            port = self.pick_port()
        if netloc is None:
            netloc = "%s.example.com" % self.make_name("netloc").lower()
            if isinstance(port, int) and not isinstance(port, bool):
                netloc += ":%d" % port
        if path is None:
            # A leading forward-slash will be added in geturl() if we
            # don't, so ensure it's here now so tests can compare URLs
            # without worrying about it.
            path = self.make_name("/path")
        else:
            # Same here with the forward-slash prefix.
            if not path.startswith("/"):
                path = "/" + path
        if params is None:
            params = self.make_name("params")
        if query is None:
            query = self.make_name("query")
        if fragment is None:
            fragment = self.make_name("fragment")
        return urllib.parse.ParseResult(
            scheme, netloc, path, params, query, fragment
        )

    def make_url(
        self,
        scheme=None,
        netloc=None,
        path=None,
        params=None,
        query=None,
        fragment=None,
    ):
        """Generate a random URL.

        Contains randomly generated values for all parts of a URL: scheme,
        location, path, parameters, query, and fragment. However, each part
        can be overridden individually.

        :return: string
        """
        return self.make_parsed_url(
            scheme, netloc, path, params, query, fragment
        ).geturl()

    def make_simple_http_url(self, netloc=None, path=None, port=None):
        """Create an arbitrary HTTP URL with only a location and path."""
        return self.make_parsed_url(
            scheme="http",
            netloc=netloc,
            path=path,
            port=port,
            params="",
            query="",
            fragment="",
        ).geturl()

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
        tarball = os.path.join(location, "%s.tar.gz" % self.make_name())
        with TempDirectory() as working_dir:
            source = working_dir.path
            for name, content in contents.items():
                self.make_file(source, name, content)

            subprocess.check_call(["tar", "-C", source, "-czf", tarball, "."])

        return tarball

    def make_response(self, status_code, content, content_type=None):
        """Return a similar response to that which `urllib` returns."""
        headers = http.client.HTTPMessage()
        if content_type is not None:
            headers.set_type(content_type)
        return urllib.request.addinfourl(
            fp=io.BytesIO(content), headers=headers, url=None, code=status_code
        )

    def make_streams(self, stdin=None, stdout=None, stderr=None):
        """Make a fake return value for a SSHClient.exec_command."""
        # stdout.read() is called so stdout can't be None.
        if stdout is None:
            stdout = mock.Mock()

        return (stdin, stdout, stderr)

    def make_CalledProcessError(self):
        """Make a fake :py:class:`subprocess.CalledProcessError`."""
        return subprocess.CalledProcessError(
            returncode=random.randint(1, 10),
            cmd=[self.make_name("command")],
            output=factory.make_bytes(),
        )

    def make_kernel_string(
        self, can_be_release_or_version=False, generic_only=False
    ):
        ubuntu = UbuntuDistroInfo()
        # Only select from MAAS supported releases so we don't have to deal
        # with versions name overlap(e.g Warty and Wily).
        try:
            ubuntu_rows = ubuntu._rows
        except AttributeError:
            ubuntu_rows = [row.__dict__ for row in ubuntu._releases]
        supported_releases = [
            release
            for release in ubuntu_rows
            if int(release["version"].split(".")[0]) >= 12
        ]
        release = random.choice(supported_releases)
        # Remove 'LTS' from version if it exists
        version_str = release["version"].split(" ")[0]
        strings = [
            "hwe-%s" % release["series"][0],
            "hwe-%s" % version_str,
            "hwe-%s-edge" % version_str,
        ]
        if not generic_only:
            strings += [
                "hwe-%s-lowlatency" % version_str,
                "hwe-%s-lowlatency-edge" % version_str,
            ]
        if can_be_release_or_version:
            strings += [release["series"], version_str]
        return random.choice(strings)

    def make_dhcp_packet(
        self,
        transaction_id: bytes = None,
        truncated: bool = False,
        truncated_option_value: bool = False,
        bad_cookie: bool = False,
        truncated_option_length: bool = False,
        include_server_identifier: bool = False,
        server_ip: str = "127.1.1.1",
        include_end_option: bool = True,
    ) -> bytes:
        """Returns a [possibly invalid] DHCP packet."""
        if transaction_id is None:
            transaction_id = self.make_bytes(size=4)
        options = b""
        if include_server_identifier:
            # 0x36 == 54 (Server Identifier option)
            ip_bytes = int(IPAddress(server_ip).value).to_bytes(4, "big")
            options += b"\x36\x04" + ip_bytes
        if truncated_option_value:
            options += b"\x36\x04\x7f\x01"
            include_end_option = False
        if truncated_option_length:
            options += b"\x36"
            include_end_option = False
        # Currently, we only validation the transaction ID, and the fact that
        # the reply packet has a "Server Identifier" option. This might be
        # considered a bug, but in practice it works out.
        packet = (
            # Message type: 0x02 (BOOTP operation: reply).
            b"\x02"
            # Hardware type: Ethernet
            b"\x01"
            # Hardware address length: 6
            b"\x06"
            # Hops: 0
            b"\x00"
            +
            # Transaction ID
            transaction_id
            +
            # Seconds
            b"\x00\x00"
            # Flags
            b"\x00\x00"
            # Client IP address: 0.0.0.0
            b"\x00\x00\x00\x00"
            # Your (client) IP address: 0.0.0.0
            b"\x00\x00\x00\x00"
            # Next server IP address: 0.0.0.0
            b"\x00\x00\x00\x00"
            # Relay agent IP address: 0.0.0.0
            b"\x00\x00\x00\x00"
            +
            # Client hardware address
            b"\x01\x02\x03\x04\x05\x06"
            # Hardware address padding
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            +
            # Server host name
            (b"\x00" * 67)
            +
            # Boot filename
            (b"\x00" * 125)
            +
            # Cookie
            (b"\x63\x82\x53\x63" if not bad_cookie else b"xxxx")
            +
            # "DHCP Offer" option
            b"\x35\x01\x02"
            + options
            +
            # End options.
            (b"\xff" if include_end_option else b"")
        )
        if truncated:
            packet = packet[:200]
        return packet


# Create factory singleton.
factory = Factory()
