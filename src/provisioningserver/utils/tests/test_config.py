# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.utils.config`."""

import os.path
import random
import re
import uuid

import formencode

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import config


class TestSchema(MAASTestCase):
    """Tests for `Schema`."""

    def test_inherits_from_formencode(self):
        self.assertIsInstance(config.Schema(), formencode.Schema)


class TestSchemaIterators(MAASTestCase):
    """Tests for `Schema._value_is_iterator` with iterators."""

    scenarios = (
        (set.__qualname__, dict(example=set())),
        (tuple.__qualname__, dict(example=tuple())),
        (list.__qualname__, dict(example=list())),
    )

    def test_recognises_iterators(self):
        self.assertTrue(config.Schema()._value_is_iterator(self.example))


class TestSchemaNonIterators(MAASTestCase):
    """Tests for `Schema._value_is_iterator` with non-iterators."""

    scenarios = (
        (bytes.__qualname__, dict(example=b"")),
        (str.__qualname__, dict(example="")),
        ("None", dict(example=None)),
    )

    def test_recognises_non_iterators(self):
        self.assertFalse(config.Schema()._value_is_iterator(self.example))


class TestByteString(MAASTestCase):
    """Tests for `ByteString`."""

    def test_converting_from_python_accepts_byte_string(self):
        example = factory.make_bytes()
        validator = config.ByteString()
        self.assertEqual(example, validator.from_python(example))

    def test_converting_from_python_rejects_non_byte_string(self):
        example = factory.make_string()
        validator = config.ByteString()
        error = self.assertRaises(
            formencode.Invalid, validator.from_python, example
        )
        self.assertEqual(
            str(error),
            f"The input must be a byte string (not a str: {example!r})",
        )

    def test_converting_to_python_accepts_byte_string(self):
        example = factory.make_bytes()
        validator = config.ByteString()
        self.assertEqual(example, validator.to_python(example))

    def test_converting_to_python_rejects_non_byte_string(self):
        example = factory.make_string()
        validator = config.ByteString()
        error = self.assertRaises(
            formencode.Invalid, validator.to_python, example
        )
        self.assertEqual(
            str(error),
            f"The input must be a byte string (not a str: {example!r})",
        )

    def test_empty_value(self):
        validator = config.ByteString()
        self.assertEqual(b"", validator.to_python(None))


class TestUUIDString(MAASTestCase):
    """Tests for `UUIDString`."""

    def test_validation_succeeds_when_uuid_is_good(self):
        example_uuid = str(uuid.uuid4())
        validator = config.UUIDString(accept_python=False)
        self.assertEqual(example_uuid, validator.from_python(example_uuid))
        self.assertEqual(example_uuid, validator.to_python(example_uuid))

    def test_validation_fails_when_uuid_is_bad(self):
        example_uuid = str(uuid.uuid4()) + "can't-be-a-uuid"
        validator = config.UUIDString(accept_python=False)
        expected_exception = self.assertRaisesRegex(
            formencode.validators.Invalid,
            "^%s$" % re.escape("%r Failed to parse UUID" % example_uuid),
        )
        with expected_exception:
            validator.from_python(example_uuid)
        with expected_exception:
            validator.to_python(example_uuid)


class TestUnicodeString(MAASTestCase):
    """Tests for `UnicodeString`."""

    def test_converting_from_python_accepts_Unicode_string(self):
        example = factory.make_string()
        validator = config.UnicodeString()
        self.assertEqual(example, validator.from_python(example))

    def test_converting_from_python_rejects_non_Uncode_string(self):
        example = factory.make_bytes()
        validator = config.UnicodeString()
        error = self.assertRaises(
            formencode.Invalid, validator.from_python, example
        )
        self.assertEqual(
            str(error),
            f"The input must be a Unicode string (not a bytes: {example!r})",
        )

    def test_converting_to_python_accepts_Unicode_string(self):
        example = factory.make_string()
        validator = config.UnicodeString()
        self.assertEqual(example, validator.to_python(example))

    def test_converting_to_python_rejects_non_Unicode_string(self):
        example = factory.make_bytes()
        validator = config.UnicodeString()
        error = self.assertRaises(
            formencode.Invalid, validator.to_python, example
        )
        self.assertEqual(
            str(error),
            f"The input must be a Unicode string (not a bytes: {example!r})",
        )

    def test_empty_value(self):
        validator = config.UnicodeString()
        self.assertEqual("", validator.to_python(None))


class TestDirectory(MAASTestCase):
    """Tests for `DirectoryString`."""

    def test_validation_succeeds_when_directory_exists(self):
        directory = self.make_dir()
        validator = config.DirectoryString(accept_python=False)
        self.assertEqual(directory, validator.from_python(directory))
        self.assertEqual(directory, validator.to_python(directory))

    def test_validation_fails_when_directory_does_not_exist(self):
        directory = os.path.join(self.make_dir(), "not-here")
        validator = config.DirectoryString(accept_python=False)
        expected_exception = self.assertRaisesRegex(
            formencode.validators.Invalid,
            "^%s$"
            % re.escape("%r does not exist or is not a directory" % directory),
        )
        with expected_exception:
            validator.from_python(directory)
        with expected_exception:
            validator.to_python(directory)


class TestExtendedURL(MAASTestCase):
    """Tests for `ExtendedURL`."""

    def setUp(self):
        super().setUp()
        self.validator = config.ExtendedURL(
            require_tld=False, accept_python=False
        )

    def test_takes_numbers_anywhere(self):
        # Could use factory.make_string() here, as it contains
        # digits, but this is a little bit more explicit and
        # clear to troubleshoot.

        hostname = "%dstart" % random.randint(0, 9)
        url = factory.make_simple_http_url(netloc=hostname)

        hostname = "mid%ddle" % random.randint(0, 9)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        hostname = "end%d" % random.randint(0, 9)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

    def test_takes_hyphen_but_not_start_or_end(self):
        # Reject leading hyphen
        hostname = "-start"
        url = factory.make_simple_http_url(netloc=hostname)
        with self.assertRaisesRegex(
            formencode.Invalid, "That is not a valid URL"
        ):
            self.assertEqual(
                url, self.validator.to_python(url), "url: %s" % url
            )

        # Allow hyphens in the middle
        hostname = "mid-dle"
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject trailing hyphen
        hostname = "end-"
        url = factory.make_simple_http_url(netloc=hostname)
        with self.assertRaisesRegex(
            formencode.Invalid, "That is not a valid URL"
        ):
            self.assertEqual(
                url, self.validator.to_python(url), "url: %s" % url
            )

    def test_allows_hostnames_as_short_as_a_single_char(self):
        # Single digit
        hostname = str(random.randint(0, 9))
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Single char
        hostname = factory.make_string(1)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject single hyphen
        hostname = "-"
        url = factory.make_simple_http_url(netloc=hostname)
        with self.assertRaisesRegex(
            formencode.Invalid, "That is not a valid URL"
        ):
            self.assertEqual(
                url, self.validator.to_python(url), "url: %s" % url
            )

    def test_allows_hostnames_up_to_63_chars_long(self):
        max_length = 63

        # Alow 63 chars
        hostname = factory.make_string(max_length)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject 64 chars
        hostname = factory.make_string(max_length + 1)
        url = factory.make_simple_http_url(netloc=hostname)
        with self.assertRaisesRegex(
            formencode.Invalid, "That is not a valid URL"
        ):
            self.assertEqual(
                url, self.validator.to_python(url), "url: %s" % url
            )

    def test_allows_domain_names_up_to_63_chars_long(self):
        max_length = 63

        # Alow 63 chars without hypen
        hostname = "%s.example.com" % factory.make_string(max_length)
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject 64 chars without hypen
        hostname = "%s.example.com" % factory.make_string(max_length + 1)
        url = factory.make_simple_http_url(netloc=hostname)
        with self.assertRaisesRegex(
            formencode.Invalid, "That is not a valid URL"
        ):
            self.assertEqual(
                url, self.validator.to_python(url), "url: %s" % url
            )

        # Alow 63 chars with hypen
        hyphen_loc = random.randint(1, max_length - 1)
        name = factory.make_string(max_length - 1)
        hname = name[:hyphen_loc] + "-" + name[hyphen_loc:]
        hostname = "%s.example.com" % hname
        url = factory.make_simple_http_url(netloc=hostname)
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # Reject 64 chars with hypen
        hyphen_loc = random.randint(1, max_length)
        name = factory.make_string(max_length)
        hname = name[:hyphen_loc] + "-" + name[hyphen_loc:]
        hostname = "%s.example.com" % hname
        url = factory.make_simple_http_url(netloc=hostname)
        with self.assertRaisesRegex(
            formencode.Invalid, "That is not a valid URL"
        ):
            self.assertEqual(
                url, self.validator.to_python(url), "url: %s" % url
            )

    def test_requires_brackets_on_ipv6_address(self):
        name = "[%s]" % factory.make_ipv6_address()
        url = factory.make_simple_http_url(
            netloc=name, port=factory.pick_bool()
        )
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

        # rejects bare ipv6 address
        name = "%s" % factory.make_ipv6_address()
        url = factory.make_simple_http_url(netloc=name)
        with self.assertRaisesRegex(
            formencode.Invalid, "That is not a valid URL"
        ):
            self.assertEqual(
                url, self.validator.to_python(url), "url: %s" % url
            )

    def test_allows_ipv4_addresses(self):
        name = "%s" % factory.make_ipv4_address()
        url = factory.make_simple_http_url(
            netloc=name, port=factory.pick_bool()
        )
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

    def test_allows_ipv4_addresses_in_ipv6_format(self):
        name = "[::ffff:%s]" % factory.make_ipv4_address()
        url = factory.make_simple_http_url(
            netloc=name, port=factory.pick_bool()
        )
        self.assertEqual(url, self.validator.to_python(url), "url: %s" % url)

    def test_allows_trailing_and_starting_double_colon(self):
        # we get random network addresses above, but lets play with a few that
        # we know need to work.
        addrs = ["::1", "::f", "fe80::", "fe80::1", "fe80:37::3:1"]
        for addr in addrs:
            # lower case
            url = factory.make_simple_http_url(
                netloc="[%s]" % addr, port=factory.pick_bool()
            )
            self.assertEqual(
                url, self.validator.to_python(url), "url: %s" % url
            )
            # upper case
            url = factory.make_simple_http_url(
                netloc="[%s]" % addr.upper(), port=factory.pick_bool()
            )
            self.assertEqual(
                url, self.validator.to_python(url), "url: %s" % url
            )


class TestOneWayStringBool(MAASTestCase):
    """Tests for `OneWayStringBool`."""

    def test_from_python(self):
        validator = config.OneWayStringBool()
        self.assertFalse(validator.from_python(False))
        self.assertTrue(validator.from_python(True))
