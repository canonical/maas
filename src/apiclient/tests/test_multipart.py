# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test multipart MIME helpers."""

from io import BytesIO
from os import urandom
from pathlib import Path

from django.utils.datastructures import MultiValueDict
from fixtures import TempDir

from apiclient.multipart import encode_multipart_data, get_content_type
from apiclient.testing.django import APIClientTestCase
from maastesting.factory import factory

ahem_django_ahem = (
    "If the mismatch appears to be because the parsed values "
    "are base64 encoded, then check you're using a >=1.4 release "
    "of Django."
)


class TestMultiPart(APIClientTestCase):
    def test_get_content_type_guesses_type(self):
        guess = get_content_type("text.txt")
        self.assertEqual("text/plain", guess)
        self.assertIsInstance(guess, str)

    def test_encode_multipart_data_produces_str(self):
        data = {factory.make_string(): factory.make_string().encode("ascii")}
        files = {
            factory.make_string(): (
                BytesIO(factory.make_string().encode("ascii"))
            )
        }
        body, headers = encode_multipart_data(data, files)
        self.assertIsInstance(body, str)

    def test_encode_multipart_data_closes_with_closing_boundary_line(self):
        data = {"foo": factory.make_string().encode("ascii")}
        files = {"bar": BytesIO(factory.make_string().encode("ascii"))}
        body, headers = encode_multipart_data(data, files)
        self.assertTrue(body.endswith("--"))

    def test_encode_multipart_data(self):
        # The encode_multipart_data() function should take a list of
        # parameters and files and encode them into a MIME
        # multipart/form-data suitable for posting to the MAAS server.
        params = {"op": "add", "foo": "bar\u1234"}
        random_data = urandom(32)
        files = {"baz": BytesIO(random_data)}
        body, headers = encode_multipart_data(params, files)
        self.assertEqual("%s" % len(body), headers["Content-Length"])
        self.assertTrue(
            headers["Content-Type"].startswith(
                "multipart/form-data; boundary="
            )
        )
        # Round-trip through Django's multipart code.
        post, files = self.parse_headers_and_body_with_django(headers, body)
        self.assertEqual(
            {name: [value] for name, value in params.items()},
            post,
            ahem_django_ahem,
        )
        self.assertSetEqual({"baz"}, set(files))
        self.assertEqual(random_data, files["baz"].read(), ahem_django_ahem)

    def test_encode_multipart_data_multiple_params(self):
        tmpdir = Path(self.useFixture(TempDir()).path)
        file2 = tmpdir / "file2"
        file2.write_text("f2")
        file3 = tmpdir / "file3"
        file3.write_text("f3")
        # Sequences of parameters and files passed to
        # encode_multipart_data() permit use of the same name for
        # multiple parameters and/or files. See `make_payloads` to
        # understand how it processes different types of parameter
        # values.
        params_in = [("one", "ABC"), ("one", "XYZ"), ("two", ["DEF", "UVW"])]
        files_in = [
            ("f-one", BytesIO(b"f1")),
            ("f-two", file2.open("rb")),
            ("f-three", lambda: file3.open("rb")),
        ]
        body, headers = encode_multipart_data(params_in, files_in)
        self.assertEqual("%s" % len(body), headers["Content-Length"])
        self.assertTrue(
            headers["Content-Type"].startswith(
                "multipart/form-data; boundary="
            )
        )
        # Round-trip through Django's multipart code.
        params_out, files_out = self.parse_headers_and_body_with_django(
            headers, body
        )
        params_out_expected = MultiValueDict()
        params_out_expected.appendlist("one", "ABC")
        params_out_expected.appendlist("one", "XYZ")
        params_out_expected.appendlist("two", "DEF")
        params_out_expected.appendlist("two", "UVW")
        self.assertEqual(params_out_expected, params_out, ahem_django_ahem)
        files_expected = {"f-one": b"f1", "f-two": b"f2", "f-three": b"f3"}
        files_observed = {name: buf.read() for name, buf in files_out.items()}
        self.assertEqual(files_expected, files_observed, ahem_django_ahem)

    def test_encode_multipart_data_list_params(self):
        params_in = [("one", ["ABC", "XYZ"]), ("one", "UVW")]
        body, headers = encode_multipart_data(params_in, [])
        params_out, files_out = self.parse_headers_and_body_with_django(
            headers, body
        )
        self.assertEqual({"one": ["ABC", "XYZ", "UVW"]}, params_out)
        self.assertSetEqual(set(), set(files_out))
