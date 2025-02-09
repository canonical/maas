# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.webhook`."""

import base64
from http import HTTPStatus
import random
from unittest.mock import call, Mock

from twisted.internet.defer import fail, inlineCallbacks, succeed
from twisted.web.client import PartialDownloadError
from twisted.web.http_headers import Headers

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.power import PowerActionError
import provisioningserver.drivers.power.webhook as webhook_module
from provisioningserver.utils.version import get_running_version


class TestWebhookPowerDriver(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    def setUp(self):
        super().setUp()
        self.webhook = webhook_module.WebhookPowerDriver()

    def test_make_auth_headers(self):
        system_id = factory.make_name("system_id")
        self.assertEqual(
            Headers(
                {
                    b"User-Agent": [f"MAAS {get_running_version()}".encode()],
                    b"Accept": [b"application/json"],
                    b"System_Id": [system_id.encode()],
                }
            ),
            self.webhook._make_auth_headers(system_id, {}),
        )

    def test_make_auth_headers_username_pass(self):
        system_id = factory.make_name("system_id")
        power_user = factory.make_name("power_user")
        power_pass = factory.make_name("power_pass")

        self.assertEqual(
            Headers(
                {
                    b"User-Agent": [f"MAAS {get_running_version()}".encode()],
                    b"Accept": [b"application/json"],
                    b"System_Id": [system_id.encode()],
                    b"Authorization": [
                        (
                            b"Basic "
                            + base64.b64encode(
                                f"{power_user}:{power_pass}".encode()
                            )
                        )
                    ],
                }
            ),
            self.webhook._make_auth_headers(
                system_id, {"power_user": power_user, "power_pass": power_pass}
            ),
        )

    def test_make_auth_headers_token(self):
        system_id = factory.make_name("system_id")
        power_user = factory.make_name("power_user")
        power_pass = factory.make_name("power_pass")
        power_token = factory.make_name("power_token")

        self.assertEqual(
            Headers(
                {
                    b"User-Agent": [f"MAAS {get_running_version()}".encode()],
                    b"Accept": [b"application/json"],
                    b"System_Id": [system_id.encode()],
                    b"Authorization": [f"Bearer {power_token}".encode()],
                }
            ),
            self.webhook._make_auth_headers(
                system_id,
                {
                    "power_user": power_user,
                    "power_pass": power_pass,
                    "power_token": power_token,
                },
            ),
        )

    def test_make_auth_headers_extra_headers(self):
        system_id = factory.make_name("system_id")
        key = factory.make_name("key").encode()
        value = factory.make_name("value").encode()
        self.assertEqual(
            Headers(
                {
                    b"User-Agent": [f"MAAS {get_running_version()}".encode()],
                    b"Accept": [b"application/json"],
                    b"System_Id": [system_id.encode()],
                    key: [value],
                }
            ),
            self.webhook._make_auth_headers(system_id, {}, {key: [value]}),
        )

    @inlineCallbacks
    def test_webhook_request_trailing_slash(self):
        mock_agent = self.patch(webhook_module, "Agent")
        mock_agent.return_value.request = Mock()
        expected_headers = Mock()
        expected_headers.code = HTTPStatus.OK
        expected_headers.headers = "Testing Headers"
        mock_agent.return_value.request.return_value = succeed(
            expected_headers
        )
        mock_readBody = self.patch(webhook_module, "readBody")
        expected_response = factory.make_name("body")
        mock_readBody.return_value = succeed(expected_response.encode())
        method = random.choice([b"POST", b"GET"])
        headers = self.webhook._make_auth_headers(
            factory.make_name("system_id"), {}
        )

        response = yield self.webhook._webhook_request(
            method,
            headers,
            b"https://10.0.0.42/",
        )
        self.assertEqual(expected_response, response.decode())
        mock_agent.return_value.request.assert_called_once_with(
            method,
            headers,
            b"https://10.0.0.42/",
            None,
        )

    @inlineCallbacks
    def test_webhook_request_retries_404s_trailing_slash(self):
        mock_agent = self.patch(webhook_module, "Agent")
        mock_agent.return_value.request = Mock()
        expected_headers = Mock()
        expected_headers.code = HTTPStatus.NOT_FOUND
        expected_headers.headers = "Testing Headers"
        happy_headers = Mock()
        happy_headers.code = HTTPStatus.OK
        happy_headers.headers = "Testing Headers"
        mock_agent.return_value.request.side_effect = [
            succeed(expected_headers),
            succeed(happy_headers),
        ]
        mock_readBody = self.patch(webhook_module, "readBody")
        expected_response = factory.make_name("body")
        mock_readBody.return_value = succeed(expected_response.encode())
        method = random.choice([b"POST", b"GET"])
        headers = self.webhook._make_auth_headers(
            factory.make_name("system_id"), {}
        )

        response = yield self.webhook._webhook_request(
            method, b"https://10.0.0.42", headers
        )
        mock_agent.return_value.request.assert_has_calls(
            [
                call(method, b"https://10.0.0.42", headers, None),
                call(method, b"https://10.0.0.42/", headers, None),
            ]
        )
        self.assertEqual(expected_response, response.decode())

    @inlineCallbacks
    def test_webhook_request_continues_partial_download_error(self):
        mock_agent = self.patch(webhook_module, "Agent")
        mock_agent.return_value.request = Mock()
        expected_headers = Mock()
        expected_headers.code = HTTPStatus.OK
        expected_headers.headers = "Testing Headers"
        mock_agent.return_value.request.return_value = succeed(
            expected_headers
        )
        mock_readBody = self.patch(webhook_module, "readBody")
        expected_response = factory.make_name("body")
        error = PartialDownloadError(
            response=expected_response.encode(),
            code=HTTPStatus.OK,
        )
        mock_readBody.return_value = fail(error)
        method = random.choice([b"POST", b"GET"])
        headers = self.webhook._make_auth_headers(
            factory.make_name("system_id"), {}
        )

        response = yield self.webhook._webhook_request(
            method, b"https://10.0.0.42", headers
        )
        self.assertEqual(expected_response, response.decode())

    @inlineCallbacks
    def test_webhook_request_raises_failures(self):
        mock_agent = self.patch(webhook_module, "Agent")
        mock_agent.return_value.request = Mock()
        expected_headers = Mock()
        expected_headers.code = HTTPStatus.OK
        expected_headers.headers = "Testing Headers"
        mock_agent.return_value.request.return_value = succeed(
            expected_headers
        )
        mock_readBody = self.patch(webhook_module, "readBody")
        expected_response = factory.make_name("body")
        error = PartialDownloadError(
            response=expected_response.encode(),
            code=HTTPStatus.NOT_FOUND,
        )
        mock_readBody.return_value = fail(error)
        method = random.choice([b"POST", b"GET"])

        with self.assertRaisesRegex(PartialDownloadError, "^404 Not Found$"):
            yield self.webhook._webhook_request(
                method, b"https://10.0.0.42", {}
            )
        mock_readBody.assert_called_once_with(expected_headers)

    @inlineCallbacks
    def test_webhook_request_raises_error_on_response_code_above_400(self):
        mock_agent = self.patch(webhook_module, "Agent")
        mock_agent.return_value.request = Mock()
        expected_headers = Mock()
        expected_headers.code = HTTPStatus.BAD_REQUEST
        expected_headers.headers = "Testing Headers"
        mock_agent.return_value.request.return_value = succeed(
            expected_headers
        )
        mock_readBody = self.patch(webhook_module, "readBody")
        method = random.choice([b"POST", b"GET"])

        with self.assertRaisesRegex(
            PowerActionError,
            f"with response status code: {HTTPStatus.BAD_REQUEST}",
        ):
            yield self.webhook._webhook_request(
                method, b"https://10.0.0.42", {}
            )
        mock_readBody.assert_not_called()

    def test_missing_packages(self):
        self.assertEqual([], self.webhook.detect_missing_packages())

    def test_power_on(self):
        mock_webhook_request = self.patch(self.webhook, "_webhook_request")
        system_id = factory.make_name("system_id")
        power_on_uri = factory.make_url()

        self.webhook.power_on(system_id, {"power_on_uri": power_on_uri})

        mock_webhook_request.assert_called_once_with(
            b"POST",
            power_on_uri.encode(),
            self.webhook._make_auth_headers(system_id, {}),
            False,
        )

    def test_power_off(self):
        mock_webhook_request = self.patch(self.webhook, "_webhook_request")
        system_id = factory.make_name("system_id")
        power_off_uri = factory.make_url()

        self.webhook.power_off(system_id, {"power_off_uri": power_off_uri})

        mock_webhook_request.assert_called_once_with(
            b"POST",
            power_off_uri.encode(),
            self.webhook._make_auth_headers(system_id, {}),
            False,
        )

    @inlineCallbacks
    def test_power_query_on(self):
        mock_webhook_request = self.patch(self.webhook, "_webhook_request")
        mock_webhook_request.return_value = succeed(b"{'status': 'running'}")
        system_id = factory.make_name("system_id")
        power_query_uri = factory.make_url()
        context = {
            "power_query_uri": power_query_uri,
            "power_on_regex": r"status.*\:.*running",
        }

        status = yield self.webhook.power_query(system_id, context)

        self.assertEqual("on", status)
        mock_webhook_request.assert_called_once_with(
            b"GET",
            power_query_uri.encode(),
            self.webhook._make_auth_headers(system_id, context),
            False,
        )

    @inlineCallbacks
    def test_power_query_off(self):
        mock_webhook_request = self.patch(self.webhook, "_webhook_request")
        mock_webhook_request.return_value = succeed(b"{'status': 'stopped'}")
        system_id = factory.make_name("system_id")
        power_query_uri = factory.make_url()
        context = {
            "power_query_uri": power_query_uri,
            "power_off_regex": r"status.*\:.*stopped",
        }

        status = yield self.webhook.power_query(system_id, context)

        self.assertEqual("off", status)
        mock_webhook_request.assert_called_once_with(
            b"GET",
            power_query_uri.encode(),
            self.webhook._make_auth_headers(system_id, context),
            False,
        )

    @inlineCallbacks
    def test_power_query_unknown(self):
        mock_webhook_request = self.patch(self.webhook, "_webhook_request")
        mock_webhook_request.return_value = succeed(
            factory.make_string().encode()
        )
        system_id = factory.make_name("system_id")
        power_query_uri = factory.make_url()
        context = {
            "power_query_uri": power_query_uri,
        }

        status = yield self.webhook.power_query(system_id, context)

        self.assertEqual("unknown", status)
        mock_webhook_request.assert_called_once_with(
            b"GET",
            power_query_uri.encode(),
            self.webhook._make_auth_headers(system_id, context),
            False,
        )
