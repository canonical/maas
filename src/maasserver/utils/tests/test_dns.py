# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test DNS utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )
from math import pow

from django.core.exceptions import ValidationError
from maasserver.utils.dns import (
    get_ip_based_hostname,
    validate_domain_name,
    validate_hostname,
)
from testtools.matchers import (
    Equals,
    HasLength,
)


str = None

__metaclass__ = type
__all__ = []


from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestHostnameValidator(MAASTestCase):
    """Tests for the validation of hostnames.

    Specifications based on:
        http://en.wikipedia.org/wiki/Hostname#Restrictions_on_valid_host_names

    This does not support Internationalized Domain Names.  To do so, we'd have
    to accept and store unicode, but use the Punycode-encoded version.  The
    validator would have to validate both versions: the unicode input for
    invalid characters, and the encoded version for length.
    """
    def make_maximum_hostname(self):
        """Create a hostname of the maximum permitted length.

        The maximum permitted length is 255 characters.  The last label in the
        hostname will not be of the maximum length, so tests can still append a
        character to it without creating an invalid label.

        The hostname is not randomised, so do not count on it being unique.
        """
        # A hostname may contain any number of labels, separated by dots.
        # Each of the labels has a maximum length of 63 characters, so this has
        # to be built up from multiple labels.
        ten_chars = ('a' * 9) + '.'
        hostname = ten_chars * 25 + ('b' * 5)
        self.assertThat(hostname, HasLength(255))
        return hostname

    def assertAccepts(self, hostname):
        """Assertion: the validator accepts `hostname`."""
        try:
            validate_hostname(hostname)
        except ValidationError as e:
            raise AssertionError(unicode(e))

    def assertRejects(self, hostname):
        """Assertion: the validator rejects `hostname`."""
        self.assertRaises(ValidationError, validate_hostname, hostname)

    def assertDomainValidatorAccepts(self, domain_name):
        """Assertion: the validator rejects `domain_name`."""
        try:
            validate_domain_name(domain_name)
        except ValidationError as e:
            raise AssertionError(unicode(e))

    def assertDomainValidatorRejects(self, hostname):
        """Assertion: the validator rejects `hostname`."""
        self.assertRaises(ValidationError, validate_domain_name, hostname)

    def test_accepts_ascii_letters(self):
        self.assertAccepts('abcde')

    def test_accepts_dots(self):
        self.assertAccepts('abc.def')

    def test_accepts_subdomain(self):
        self.assertAccepts('abc.def.ubuntu.com')

    def test_rejects_adjacent_dots(self):
        self.assertRejects('abc..def')

    def test_rejects_leading_dot(self):
        self.assertRejects('.abc')

    def test_rejects_trailing_dot(self):
        self.assertRejects('abc.')

    def test_accepts_ascii_digits(self):
        self.assertAccepts('abc123')

    def test_accepts_leading_digits(self):
        # Leading digits used to be forbidden, but are now allowed.
        self.assertAccepts('123abc')

    def test_rejects_whitespace(self):
        self.assertRejects('a b')
        self.assertRejects('a\nb')
        self.assertRejects('a\tb')

    def test_rejects_other_ascii_characters(self):
        self.assertRejects('a?b')
        self.assertRejects('a!b')
        self.assertRejects('a,b')
        self.assertRejects('a:b')
        self.assertRejects('a;b')
        self.assertRejects('a+b')
        self.assertRejects('a=b')

    def test_accepts_underscore_in_domain(self):
        self.assertAccepts('host.local_domain')

    def test_rejects_underscore_in_host(self):
        self.assertRejects('host_name.local')

    def test_accepts_hyphen(self):
        self.assertAccepts('a-b')

    def test_rejects_hyphen_at_start_of_label(self):
        self.assertRejects('-ab')

    def test_rejects_hyphen_at_end_of_label(self):
        self.assertRejects('ab-')

    def test_accepts_maximum_valid_length(self):
        self.assertAccepts(self.make_maximum_hostname())

    def test_rejects_oversized_hostname(self):
        self.assertRejects(self.make_maximum_hostname() + 'x')

    def test_accepts_maximum_label_length(self):
        self.assertAccepts('a' * 63)

    def test_rejects_oversized_label(self):
        self.assertRejects('b' * 64)

    def test_rejects_nonascii_letter(self):
        # The \u03be is the Greek letter xi.  Perfectly good letter, just not
        # ASCII.
        self.assertRejects('\u03be')

    def test_accepts_domain_underscores(self):
        self.assertDomainValidatorAccepts('_foo')
        self.assertDomainValidatorAccepts('_foo._bar')
        self.assertDomainValidatorAccepts('_.o_O._')


class TestIpBasedHostnameGenerator(MAASTestCase):

    def test_ipv4_numeric(self):
        self.expectThat(
            get_ip_based_hostname(2130706433),
            Equals("127-0-0-1"))
        self.expectThat(
            get_ip_based_hostname(int(pow(2, 32) - 1)),
            Equals("255-255-255-255"))

    def test_ipv4_text(self):
        ipv4 = factory.make_ipv4_address()
        self.expectThat(
            get_ip_based_hostname(ipv4),
            Equals(ipv4.replace('.', '-')))
        self.expectThat(
            get_ip_based_hostname("172.16.0.1"),
            Equals("172-16-0-1"))

    def test_ipv6_text(self):
        ipv4 = factory.make_ipv6_address()
        self.expectThat(
            get_ip_based_hostname(ipv4),
            Equals(ipv4.replace(':', '-')))
        self.expectThat(
            get_ip_based_hostname("2001:67c:1562::15"),
            Equals("2001-67c-1562--15"))
