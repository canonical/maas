# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maas_api_helper functions."""


from collections import OrderedDict
from email.utils import formatdate
from io import StringIO
import json
from pathlib import Path
import random
import re
from subprocess import PIPE, Popen, TimeoutExpired
import time
from unittest.mock import ANY, MagicMock
import urllib

from lxml import etree
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    MatchesAll,
    MatchesAny,
    MatchesDict,
    MatchesListwise,
)

from maastesting.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.matchers import (
    GreaterThanOrEqual,
    LessThanOrEqual,
    MockAnyCall,
    MockCalledOnce,
    MockCalledOnceWith,
    MockCalledWith,
)
from maastesting.testcase import MAASTestCase
from provisioningserver.refresh import maas_api_helper


class TestHeaders(MAASTestCase):
    def test_oauth_headers(self):
        now = time.time()
        is_about_now = MatchesAll(
            GreaterThanOrEqual(int(now)), LessThanOrEqual(int(now) + 3)
        )

        url = factory.make_name("url")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        consumer_secret = factory.make_name("consumer_secret")
        headers = maas_api_helper.oauth_headers(
            url, consumer_key, token_key, token_secret, consumer_secret
        )
        authorization = headers["Authorization"]
        self.assertRegex(authorization, "^OAuth .*")
        authorization = authorization.replace("OAuth ", "")
        oauth_arguments = {}
        for argument in authorization.split(", "):
            key, value = argument.split("=")
            oauth_arguments[key] = value.replace('"', "")

        self.assertIn("oauth_nonce", oauth_arguments)
        oauth_arguments.pop("oauth_nonce", None)

        self.assertThat(
            oauth_arguments,
            MatchesDict(
                {
                    "oauth_timestamp": AfterPreprocessing(int, is_about_now),
                    "oauth_version": Equals("1.0"),
                    "oauth_signature_method": Equals("PLAINTEXT"),
                    "oauth_consumer_key": Equals(consumer_key),
                    "oauth_token": Equals(token_key),
                    "oauth_signature": Equals(
                        "%s%%26%s" % (consumer_secret, token_secret)
                    ),
                }
            ),
        )

    def test_authenticate_headers_appends_oauth(self):
        url = factory.make_name("url")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        consumer_secret = factory.make_name("consumer_secret")
        creds = {
            "consumer_key": consumer_key,
            "token_key": token_key,
            "token_secret": token_secret,
            "consumer_secret": consumer_secret,
        }
        headers = {}
        maas_api_helper.authenticate_headers(url, headers, creds)
        self.assertIn("Authorization", headers)

    def test_authenticate_headers_only_appends_with_consumer_key(self):
        headers = {}
        maas_api_helper.authenticate_headers(
            factory.make_name("url"), headers, {}
        )
        self.assertEqual({}, headers)


class MAASMockHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        if "broken_with_date" in req.get_full_url():
            code = random.choice([401, 403])
            headers = {"date": formatdate()}
        elif "broken" in req.get_full_url():
            code = 400
            headers = {}
        else:
            code = 200
            headers = {}
        resp = urllib.request.addinfourl(
            StringIO("mock response"), headers, req.get_full_url(), code
        )
        resp.msg = "OK"
        return resp


class TestGetUrl(MAASTestCase):
    def setUp(self):
        super().setUp()
        opener = urllib.request.build_opener(MAASMockHTTPHandler)
        urllib.request.install_opener(opener)

    def test_geturl_sends_request(self):
        self.assertEquals(
            "mock response",
            maas_api_helper.geturl(
                "http://%s" % factory.make_hostname(), {}
            ).read(),
        )

    def test_geturl_raises_exception_on_failure(self):
        sleep = self.patch(maas_api_helper.time, "sleep")
        warn = self.patch(maas_api_helper, "warn")
        self.assertRaises(
            urllib.error.HTTPError,
            maas_api_helper.geturl,
            "http://%s-broken" % factory.make_hostname(),
            {},
        )
        self.assertEquals(7, sleep.call_count)
        self.assertThat(warn, MockAnyCall("date field not in 400 headers"))

    def test_geturl_increments_skew(self):
        sleep = self.patch(maas_api_helper.time, "sleep")
        warn = self.patch(maas_api_helper, "warn")
        self.assertRaises(
            urllib.error.HTTPError,
            maas_api_helper.geturl,
            "http://%s-broken_with_date" % factory.make_hostname(),
            {},
        )
        self.assertEquals(7, sleep.call_count)
        clock_shew_updates = [
            call[0][0].startswith("updated clock shew to")
            for call in warn.call_args_list
        ]
        self.assertEquals(14, len(clock_shew_updates))

    def test_geturl_posts_data(self):
        mock_urlopen = self.patch(maas_api_helper.urllib.request.urlopen)
        post_data = {factory.make_name("key"): factory.make_name("value")}
        maas_api_helper.geturl(
            "http://%s" % factory.make_hostname(), post_data=post_data
        )
        self.assertThat(
            mock_urlopen,
            MockCalledOnceWith(
                ANY, urllib.parse.urlencode(post_data).encode("ascii")
            ),
        )


class TestEncode(MAASTestCase):
    def test_encode_blank(self):
        data, headers = maas_api_helper.encode_multipart_data({}, {})
        m = re.search("boundary=([a-zA-Z]+)", headers["Content-Type"])
        boundary = m.group(1)
        self.assertEqual(
            {
                "Content-Type": "multipart/form-data; boundary=%s" % boundary,
                "Content-Length": str(len(data)),
            },
            headers,
        )
        self.assertIsInstance(data, bytes)
        self.assertEquals("--%s--\r\n" % boundary, data.decode("utf-8"))

    def test_encode_data(self):
        key = factory.make_name("key")
        value = factory.make_name("value")
        params = {key.encode("utf-8"): value.encode("utf-8")}
        data, headers = maas_api_helper.encode_multipart_data(params, {})
        m = re.search("boundary=([a-zA-Z]+)", headers["Content-Type"])
        boundary = m.group(1)
        self.assertEqual(
            {
                "Content-Type": "multipart/form-data; boundary=%s" % boundary,
                "Content-Length": str(len(data)),
            },
            headers,
        )
        self.assertIsInstance(data, bytes)
        self.assertEquals(
            '--%s\r\nContent-Disposition: form-data; name="%s"'
            "\r\n\r\n%s\r\n--%s--\r\n" % (boundary, key, value, boundary),
            data.decode("utf-8"),
        )

    def test_encode_file(self):
        file = factory.make_name("file")
        content = factory.make_name("content")
        files = {file: content.encode("utf-8")}
        data, headers = maas_api_helper.encode_multipart_data({}, files)
        m = re.search("boundary=([a-zA-Z]+)", headers["Content-Type"])
        boundary = m.group(1)
        self.assertEqual(
            {
                "Content-Type": "multipart/form-data; boundary=%s" % boundary,
                "Content-Length": str(len(data)),
            },
            headers,
        )
        self.assertIsInstance(data, bytes)
        self.assertEquals(
            '--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"'
            "\r\nContent-Type: application/octet-stream\r\n\r\n%s\r\n--%s--"
            "\r\n" % (boundary, file, file, content, boundary),
            data.decode("utf-8"),
        )


class TestSignal(MAASTestCase):
    def test_signal_formats_basic_params(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(None, None, status)

        self.assertThat(
            mock_encode_multipart_data,
            MockCalledWith(
                {b"op": b"signal", b"status": status.encode("utf-8")}, {}
            ),
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_formats_params_with_error(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")
        error = factory.make_name("error")

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(None, None, status, error=error)

        self.assertThat(
            mock_encode_multipart_data,
            MockCalledWith(
                {
                    b"op": b"signal",
                    b"status": status.encode("utf-8"),
                    b"error": error.encode("utf-8"),
                },
                {},
            ),
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_formats_params_with_script_result_id(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")
        script_result_id = random.randint(1, 1000)

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(
            None, None, status, script_result_id=script_result_id
        )

        self.assertThat(
            mock_encode_multipart_data,
            MockCalledWith(
                {
                    b"op": b"signal",
                    b"status": status.encode("utf-8"),
                    b"script_result_id": str(script_result_id).encode("utf-8"),
                },
                {},
            ),
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_formats_params_with_exit_status(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")
        exit_status = random.randint(0, 255)

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(None, None, status, exit_status=exit_status)

        self.assertThat(
            mock_encode_multipart_data,
            MockCalledWith(
                {
                    b"op": b"signal",
                    b"status": status.encode("utf-8"),
                    b"exit_status": str(exit_status).encode("utf-8"),
                },
                {},
            ),
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_formats_params_with_script_name(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")
        script_name = factory.make_name("script_name")

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(None, None, status, script_name=script_name)

        self.assertThat(
            mock_encode_multipart_data,
            MockCalledWith(
                {
                    b"op": b"signal",
                    b"status": status.encode("utf-8"),
                    b"name": str(script_name).encode("utf-8"),
                },
                {},
            ),
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_formats_params_with_script_version_id(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")
        script_version_id = random.randint(1, 1000)

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(
            None, None, status, script_version_id=script_version_id
        )

        self.assertThat(
            mock_encode_multipart_data,
            MockCalledWith(
                {
                    b"op": b"signal",
                    b"status": status.encode("utf-8"),
                    b"script_version_id": str(script_version_id).encode(
                        "utf-8"
                    ),
                },
                {},
            ),
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_formats_params_with_runtime(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")
        script_name = factory.make_name("script_name")
        runtime = random.randint(1000, 9999) / 100

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(
            None, None, status, script_name=script_name, runtime=runtime
        )

        self.assertThat(
            mock_encode_multipart_data,
            MockCalledWith(
                {
                    b"op": b"signal",
                    b"status": status.encode("utf-8"),
                    b"name": str(script_name).encode("utf-8"),
                    b"runtime": str(runtime).encode("utf-8"),
                },
                {},
            ),
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_formats_params_with_power_params(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")
        power_type = factory.make_name("power_type")
        power_params = OrderedDict(
            [
                ("power_user", factory.make_name("power_user")),
                ("power_pass", factory.make_name("power_pass")),
                ("power_address", factory.make_url()),
                ("power_driver", factory.make_name("power_driver")),
                ("power_boot_type", factory.make_name("power_boot_type")),
            ]
        )

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(
            None,
            None,
            status,
            power_type=power_type,
            power_params=",".join([value for value in power_params.values()]),
        )

        # XXX ltrager 2017-01-18 - The power_parameters JSON dump breaks
        # MockCalledWith.
        self.assertDictEqual(
            mock_encode_multipart_data.call_args[0][0],
            {
                b"op": b"signal",
                b"status": status.encode("utf-8"),
                b"power_type": power_type.encode("utf-8"),
                b"power_parameters": json.dumps(power_params).encode(),
            },
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_formats_params_with_moonshot_power_params(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")
        power_type = "moonshot"
        power_params = OrderedDict(
            [
                ("power_user", factory.make_name("power_user")),
                ("power_pass", factory.make_name("power_pass")),
                ("power_address", factory.make_url()),
                ("power_hwaddress", factory.make_name("power_hwaddress")),
            ]
        )

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(
            None,
            None,
            status,
            power_type=power_type,
            power_params=",".join([value for value in power_params.values()]),
        )

        # XXX ltrager 2017-01-18 - The power_parameters JSON dump breaks
        # MockCalledWith.
        self.assertDictEqual(
            mock_encode_multipart_data.call_args[0][0],
            {
                b"op": b"signal",
                b"status": status.encode("utf-8"),
                b"power_type": power_type.encode("utf-8"),
                b"power_parameters": json.dumps(power_params).encode(),
            },
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_formats_files(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = b"OK"
        mock_geturl.return_value = mm

        status = factory.make_name("status")
        files = {factory.make_name(): factory.make_bytes()}

        # None used for url and creds as we're not actually sending data.
        maas_api_helper.signal(None, None, status, files=files)

        self.assertThat(
            mock_encode_multipart_data,
            MockCalledWith(
                {b"op": b"signal", b"status": status.encode("utf-8")}, files
            ),
        )
        self.assertThat(mock_geturl, MockCalledOnce())

    def test_signal_raises_exception_if_not_ok(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mm = MagicMock()
        mm.status = 400
        mm.read.return_value = b"bad_ret"
        mock_geturl.return_value = mm

        status = factory.make_name("status")

        # None used for url and creds as we're not actually sending data.
        self.assertRaises(
            maas_api_helper.SignalException,
            maas_api_helper.signal,
            None,
            None,
            status,
        )

    def test_signal_raises_exception_on_httperror(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mock_geturl.side_effect = maas_api_helper.urllib.error.HTTPError(
            None, None, None, None, None
        )

        status = factory.make_name("status")

        # None used for url and creds as we're not actually sending data.
        self.assertRaises(
            maas_api_helper.SignalException,
            maas_api_helper.signal,
            None,
            None,
            status,
        )

    def test_signal_raises_exception_on_urlerror(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mock_geturl.side_effect = maas_api_helper.urllib.error.URLError(None)

        status = factory.make_name("status")

        # None used for url and creds as we're not actually sending data.
        self.assertRaises(
            maas_api_helper.SignalException,
            maas_api_helper.signal,
            None,
            None,
            status,
        )

    def test_signal_raises_exception_on_socket_timeout(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mock_geturl.side_effect = maas_api_helper.socket.timeout()

        status = factory.make_name("status")

        # None used for url and creds as we're not actually sending data.
        self.assertRaises(
            maas_api_helper.SignalException,
            maas_api_helper.signal,
            None,
            None,
            status,
        )

    def test_signal_raises_exception_on_typeerror(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mock_geturl.side_effect = TypeError()

        status = factory.make_name("status")

        # None used for url and creds as we're not actually sending data.
        self.assertRaises(
            maas_api_helper.SignalException,
            maas_api_helper.signal,
            None,
            None,
            status,
        )

    def test_signal_raises_exception_on_unknown_exception(self):
        mock_encode_multipart_data = self.patch(
            maas_api_helper, "encode_multipart_data"
        )
        mock_encode_multipart_data.return_value = None, None
        mock_geturl = self.patch(maas_api_helper, "geturl")
        mock_geturl.side_effect = Exception()

        status = factory.make_name("status")

        # None used for url and creds as we're not actually sending data.
        self.assertRaises(
            maas_api_helper.SignalException,
            maas_api_helper.signal,
            None,
            None,
            status,
        )


class TestCaptureScriptOutput(MAASTestCase):
    def setUp(self):
        super().setUp()
        # Make sure output isn't shown when running tests through a console
        self.isatty = self.patch(maas_api_helper.sys.stdout, "isatty")
        self.isatty.return_value = False

    def capture(self, proc, timeout=None):
        scripts_dir = Path(self.useFixture(TempDirectory()).path)
        combined_path = scripts_dir.joinpath("combined")
        stdout_path = scripts_dir.joinpath("stdout")
        stderr_path = scripts_dir.joinpath("stderr")

        returncode = maas_api_helper.capture_script_output(
            proc,
            str(combined_path),
            str(stdout_path),
            str(stderr_path),
            timeout,
        )

        return (
            returncode,
            stdout_path.read_text(),
            stderr_path.read_text(),
            combined_path.read_text(),
        )

    def test_captures_script_output(self):
        proc = Popen(
            'echo "stdout"; echo "stderr" 1>&2',
            stdout=PIPE,
            stderr=PIPE,
            shell=True,
        )
        self.assertThat(
            self.capture(proc),
            MatchesListwise(
                (
                    Equals(0),
                    Equals("stdout\n"),
                    Equals("stderr\n"),
                    # The writes to stdout and stderr occur so close in time that
                    # they may be received in any order.
                    MatchesAny(
                        Equals("stdout\nstderr\n"), Equals("stderr\nstdout\n")
                    ),
                )
            ),
        )

    def test_forwards_to_console(self):
        stdout = self.patch(maas_api_helper.sys.stdout, "write")
        stderr = self.patch(maas_api_helper.sys.stderr, "write")
        stdout_flush = self.patch(maas_api_helper.sys.stdout, "flush")
        stderr_flush = self.patch(maas_api_helper.sys.stderr, "flush")
        self.isatty.return_value = True
        proc = Popen(
            'echo "stdout"; echo "stderr" 1>&2',
            stdout=PIPE,
            stderr=PIPE,
            shell=True,
        )
        self.capture(proc)
        self.assertThat(stdout, MockCalledOnceWith("stdout\n"))
        self.assertThat(stderr, MockCalledOnceWith("stderr\n"))
        self.assertThat(stdout_flush, MockCalledOnce())
        self.assertThat(stderr_flush, MockCalledOnce())

    def test_does_not_wait_for_forked_process(self):
        start_time = time.time()
        proc = Popen("sleep 6 &", stdout=PIPE, stderr=PIPE, shell=True)
        self.assertThat(
            self.capture(proc),
            MatchesListwise((Equals(0), Equals(""), Equals(""), Equals(""))),
        )
        # A forked process should continue running after capture_script_output
        # returns. capture_script_output should not block on the forked call.
        self.assertLess(time.time() - start_time, 3)

    def test_captures_output_from_completed_process(self):
        # Write to both stdout and stderr.
        proc = Popen(
            "echo -n foo >&1 && echo -n bar >&2",
            stdout=PIPE,
            stderr=PIPE,
            shell=True,
        )
        # Wait for it to finish before capturing.
        self.assertEquals(0, proc.wait())
        # Capturing now still gets foo and bar.
        self.assertThat(
            self.capture(proc),
            MatchesListwise(
                (
                    Equals(0),
                    Equals("foo"),
                    Equals("bar"),
                    # The writes to stdout and stderr occur so close in time that
                    # they may be received in any order.
                    MatchesAny(Equals("foobar"), Equals("barfoo")),
                )
            ),
        )

    def test_captures_stderr_after_stdout_closes(self):
        # Write to stdout, close stdout, then write to stderr.
        proc = Popen(
            "echo -n foo >&1 && exec 1>&- && echo -n bar >&2",
            stdout=PIPE,
            stderr=PIPE,
            shell=True,
        )
        # Capturing gets the bar even after stdout is closed.
        self.assertThat(
            self.capture(proc),
            MatchesListwise(
                (
                    Equals(0),
                    Equals("foo"),
                    Equals("bar"),
                    # The writes to stdout and stderr occur so close in time that
                    # they may be received in any order.
                    MatchesAny(Equals("foobar"), Equals("barfoo")),
                )
            ),
        )

    def test_captures_stdout_after_stderr_closes(self):
        # Write to stderr, close stderr, then write to stdout.
        proc = Popen(
            "echo -n bar >&2 && exec 2>&- && echo -n foo >&1",
            stdout=PIPE,
            stderr=PIPE,
            shell=True,
        )
        # Capturing gets the foo even after stderr is closed.
        self.assertThat(
            self.capture(proc),
            MatchesListwise(
                (
                    Equals(0),
                    Equals("foo"),
                    Equals("bar"),
                    # The writes to stdout and stderr occur so close in time that
                    # they may be received in any order.
                    MatchesAny(Equals("foobar"), Equals("barfoo")),
                )
            ),
        )

    def test_captures_all_output(self):
        proc = Popen(("lshw", "-xml"), stdout=PIPE, stderr=PIPE)
        returncode, stdout, stderr, combined = self.capture(proc)
        self.assertThat(returncode, Equals(0), stderr)
        # This is a complete XML document; we've captured all output.
        self.assertThat(etree.fromstring(stdout).tag, Equals("list"))

    def test_interprets_backslash(self):
        proc = Popen(
            'bash -c "echo -en \bmas\bas"',
            stdout=PIPE,
            stderr=PIPE,
            shell=True,
        )
        self.assertThat(
            self.capture(proc),
            MatchesListwise(
                (Equals(0), Equals("maas"), Equals(""), Equals("maas"))
            ),
        )

    def test_interprets_carriage_return(self):
        proc = Popen(
            'bash -c "echo -en foo\rmaas"',
            stdout=PIPE,
            stderr=PIPE,
            shell=True,
        )
        self.assertThat(
            self.capture(proc),
            MatchesListwise(
                (Equals(0), Equals("maas"), Equals(""), Equals("maas"))
            ),
        )

    def test_timeout(self):
        self.patch(maas_api_helper.time, "monotonic").side_effect = (
            0,
            60 * 6,
            60 * 6,
            60 * 6,
        )
        proc = Popen('echo "test"', stdout=PIPE, stderr=PIPE, shell=True)
        self.assertRaises(
            TimeoutExpired, self.capture, proc, random.randint(1, 5)
        )
