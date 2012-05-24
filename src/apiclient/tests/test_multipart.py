# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test multipart MIME helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from io import BytesIO
from random import randint
import re
from textwrap import dedent

from apiclient.multipart import (
    encode_field,
    encode_file,
    encode_multipart_data,
    get_content_type,
    make_random_boundary,
    )
from maastesting.factory import factory
from maastesting.testcase import TestCase
from testtools.matchers import EndsWith


class TestMultiPart(TestCase):

    def test_make_random_boundary_produces_bytes(self):
        self.assertIsInstance(make_random_boundary(), bytes)

    def test_make_random_boundary_produces_different_strings(self):
        self.assertNotEqual(
            make_random_boundary(),
            make_random_boundary())

    def test_make_random_boundary_obeys_length(self):
        length = randint(5, 100)
        self.assertEqual(length, len(make_random_boundary(length)))

    def test_make_random_boundary_uses_no_weird_characters(self):
        boundary = make_random_boundary(1000)
        self.assertTrue(boundary.isalnum())
        self.assertEqual([boundary], boundary.split())
        self.assertNotIn('-', boundary)

    def test_get_content_type_guesses_type(self):
        guess = get_content_type('text.txt')
        self.assertEqual('text/plain', guess)
        self.assertIsInstance(guess, bytes)

    def test_get_content_type_defaults_to_raw_bytes(self):
        guess = get_content_type('mysterious-data')
        self.assertEqual('application/octet-stream', guess)
        self.assertIsInstance(guess, bytes)

    def test_encode_field_encodes_form_field_as_sequence_of_byteses(self):
        name = factory.getRandomString()
        data = factory.getRandomString().encode('ascii')
        boundary = make_random_boundary(5)
        encoded_field = encode_field(name, data, boundary)
        self.assertIn(b'--' + boundary, encoded_field)
        self.assertIn(data, encoded_field)
        text = b'\n'.join(encoded_field)
        self.assertIn(b'name="%s"' % name, text)
        self.assertIsInstance(text, bytes)

    def test_encode_file_encodes_file_as_sequence_of_byteses(self):
        name = factory.getRandomString()
        data = factory.getRandomString().encode('ascii')
        boundary = make_random_boundary(5)
        encoded_file = encode_file(name, BytesIO(data), boundary)
        self.assertIn(b'--' + boundary, encoded_file)
        self.assertIn(data, encoded_file)
        text = b'\n'.join(encoded_file)
        self.assertIn(b'name="%s"' % name, text)
        self.assertIsInstance(text, bytes)

    def test_encode_multipart_data_produces_bytes(self):
        data = {
            factory.getRandomString():
                factory.getRandomString().encode('ascii'),
        }
        files = {
            factory.getRandomString():
                BytesIO(factory.getRandomString().encode('ascii')),
            }
        body, headers = encode_multipart_data(data, files)
        self.assertIsInstance(body, bytes)

    def test_encode_multipart_data_closes_with_closing_boundary_line(self):
        data = {b'foo': factory.getRandomString().encode('ascii')}
        files = {b'bar': BytesIO(factory.getRandomString().encode('ascii'))}
        body, headers = encode_multipart_data(data, files)
        self.assertThat(body, EndsWith(b'--\r\n'))

    def test_encode_multipart_data(self):
        # The encode_multipart_data() function should take a list of
        # parameters and files and encode them into a MIME
        # multipart/form-data suitable for posting to the MAAS server.
        params = {"op": "add", "filename": "foo"}
        fileObj = BytesIO(b"random data")
        files = {"file": fileObj}
        body, headers = encode_multipart_data(params, files)

        expected_body_regex = b"""\
            --(?P<boundary>.+)
            Content-Disposition: form-data; name="filename"

            foo
            --(?P=boundary)
            Content-Disposition: form-data; name="op"

            add
            --(?P=boundary)
            Content-Disposition: form-data; name="file"; filename="file"
            Content-Type: application/octet-stream

            random data
            --(?P=boundary)--
            """
        expected_body_regex = dedent(expected_body_regex)
        expected_body_regex = b"\r\n".join(expected_body_regex.splitlines())
        expected_body = re.compile(expected_body_regex, re.MULTILINE)
        self.assertRegexpMatches(body, expected_body)

        boundary = expected_body.match(body).group("boundary")
        expected_headers = {
            b"content-length": str(len(body)),
            b"content-type": b"multipart/form-data; boundary=%s" % boundary,
            }
        self.assertEqual(expected_headers, headers)
