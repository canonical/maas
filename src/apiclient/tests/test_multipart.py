# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test multipart MIME helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from io import BytesIO
from os import urandom

from apiclient.multipart import (
    encode_multipart_data,
    get_content_type,
    )
from apiclient.testing.django import parse_headers_and_body_with_django
from django.utils.datastructures import MultiValueDict
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from testtools.matchers import (
    EndsWith,
    StartsWith,
    )


ahem_django_ahem = (
    "If the mismatch appears to be because the parsed values "
    "are base64 encoded, then check you're using a >=1.4 release "
    "of Django.")


class TestMultiPart(MAASTestCase):

    def test_get_content_type_guesses_type(self):
        guess = get_content_type('text.txt')
        self.assertEqual('text/plain', guess)
        self.assertIsInstance(guess, bytes)

    def test_encode_multipart_data_produces_bytes(self):
        data = {
            factory.getRandomString(): (
                factory.getRandomString().encode('ascii')),
        }
        files = {
            factory.getRandomString(): (
                BytesIO(factory.getRandomString().encode('ascii'))),
        }
        body, headers = encode_multipart_data(data, files)
        self.assertIsInstance(body, bytes)

    def test_encode_multipart_data_closes_with_closing_boundary_line(self):
        data = {b'foo': factory.getRandomString().encode('ascii')}
        files = {b'bar': BytesIO(factory.getRandomString().encode('ascii'))}
        body, headers = encode_multipart_data(data, files)
        self.assertThat(body, EndsWith(b'--'))

    def test_encode_multipart_data(self):
        # The encode_multipart_data() function should take a list of
        # parameters and files and encode them into a MIME
        # multipart/form-data suitable for posting to the MAAS server.
        params = {"op": "add", "foo": "bar\u1234"}
        random_data = urandom(32)
        files = {"baz": BytesIO(random_data)}
        body, headers = encode_multipart_data(params, files)
        self.assertEqual("%s" % len(body), headers["Content-Length"])
        self.assertThat(
            headers["Content-Type"],
            StartsWith("multipart/form-data; boundary="))
        # Round-trip through Django's multipart code.
        post, files = parse_headers_and_body_with_django(headers, body)
        self.assertEqual(
            {name: [value] for name, value in params.items()}, post,
            ahem_django_ahem)
        self.assertSetEqual({"baz"}, set(files))
        self.assertEqual(
            random_data, files["baz"].read(),
            ahem_django_ahem)

    def test_encode_multipart_data_multiple_params(self):
        # Sequences of parameters and files can be passed to
        # encode_multipart_data() so that multiple parameters/files with the
        # same name can be provided.
        params_in = [
            ("one", "ABC"),
            ("one", "XYZ"),
            ("two", "DEF"),
            ("two", "UVW"),
            ]
        files_in = [
            ("f-one", BytesIO(urandom(32))),
            ("f-two", BytesIO(urandom(32))),
            ]
        body, headers = encode_multipart_data(params_in, files_in)
        self.assertEqual("%s" % len(body), headers["Content-Length"])
        self.assertThat(
            headers["Content-Type"],
            StartsWith("multipart/form-data; boundary="))
        # Round-trip through Django's multipart code.
        params_out, files_out = (
            parse_headers_and_body_with_django(headers, body))
        params_out_expected = MultiValueDict()
        for name, value in params_in:
            params_out_expected.appendlist(name, value)
        self.assertEqual(
            params_out_expected, params_out,
            ahem_django_ahem)
        self.assertSetEqual({"f-one", "f-two"}, set(files_out))
        files_expected = {name: buf.getvalue() for name, buf in files_in}
        files_observed = {name: buf.read() for name, buf in files_out.items()}
        self.assertEqual(
            files_expected, files_observed,
            ahem_django_ahem)

    def test_encode_multipart_data_list_params(self):
        params_in = [
            ("one", ["ABC", "XYZ"]),
            ("one", "UVW"),
            ]
        body, headers = encode_multipart_data(params_in, [])
        params_out, files_out = (
            parse_headers_and_body_with_django(headers, body))
        self.assertEqual({'one': ['ABC', 'XYZ', 'UVW']}, params_out)
        self.assertSetEqual(set(), set(files_out))
