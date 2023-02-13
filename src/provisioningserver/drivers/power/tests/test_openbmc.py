# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from io import BytesIO
import json
from os.path import join
import random

from twisted.internet._sslverify import ClientTLSOptions
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import FileBodyProducer

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith, MockCalledWith
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
import provisioningserver.drivers.power.openbmc as openbmc_module
from provisioningserver.drivers.power.openbmc import OpenBMCPowerDriver
from provisioningserver.drivers.power.utils import WebClientContextFactory

SAMPLE_JSON_HOSTOFF = {
    "data": "xyz.openbmc_project.State.Host.HostState.Off",
    "message": "200 OK",
    "status": "ok",
}

# OpenBMC RESTful uri path
HOST_STATE = "/xyz/openbmc_project/state/host0/attr/"

# OpenBMC RESTful control data
HOST_OFF = {"data": "xyz.openbmc_project.State.Host.Transition.Off"}
HOST_ON = {"data": "xyz.openbmc_project.State.Host.Transition.On"}


def make_context():
    return {
        "power_address": factory.make_ipv4_address(),
        "power_user": factory.make_name("power_user"),
        "power_pass": factory.make_name("power_pass"),
    }


class TestWebClientContextFactory(MAASTestCase):
    def test_creatorForNetloc_returns_tls_options(self):
        hostname = factory.make_name("hostname").encode("utf-8")
        port = random.randint(1000, 2000)
        contextFactory = WebClientContextFactory()
        opts = contextFactory.creatorForNetloc(hostname, port)
        self.assertIsInstance(opts, ClientTLSOptions)


class TestOpenBMCPowerDriver(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    def test_missing_packages(self):
        driver = OpenBMCPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def test_get_url_with_ip(self):
        driver = OpenBMCPowerDriver()
        context = make_context()
        ip = context.get("power_address").encode("utf-8")
        expected_url = b"https://%s" % ip
        url = driver.get_uri(context)
        self.assertEqual(expected_url, url)

    def test_get_url_with_https(self):
        driver = OpenBMCPowerDriver()
        context = make_context()
        context["power_address"] = join("https://", context["power_address"])
        expected_url = context.get("power_address").encode("utf-8")
        url = driver.get_uri(context)
        self.assertEqual(expected_url, url)

    def test_get_url_with_http(self):
        driver = OpenBMCPowerDriver()
        context = make_context()
        context["power_address"] = join("http://", context["power_address"])
        expected_url = context.get("power_address").encode("utf-8")
        url = driver.get_uri(context)
        self.assertEqual(expected_url, url)

    @inlineCallbacks
    def test_power_query_queries_on(self):
        driver = OpenBMCPowerDriver()
        power_change = "on"
        system_id = factory.make_name("system_id")
        context = make_context()
        mock_power_query = self.patch(driver, "power_query")
        mock_power_query.return_value = "on"
        power_state = yield driver.power_query(system_id, context)
        self.assertEqual(power_state, power_change)

    @inlineCallbacks
    def test_power_query_queries_off(self):
        driver = OpenBMCPowerDriver()
        power_change = "off"
        system_id = factory.make_name("system_id")
        context = make_context()
        mock_power_query = self.patch(driver, "power_query")
        mock_power_query.return_value = "off"
        power_state = yield driver.power_query(system_id, context)
        self.assertEqual(power_state, power_change)

    @inlineCallbacks
    def test_power_on(self):
        driver = OpenBMCPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        url = driver.get_uri(context, HOST_STATE + "RequestedHostTransition")
        mock_file_body_producer = self.patch(
            openbmc_module, "FileBodyProducer"
        )
        dataon = FileBodyProducer(BytesIO(json.dumps(HOST_ON).encode("utf-8")))
        mock_openbmc_request = self.patch(driver, "openbmc_request")
        mock_openbmc_request.return_value = dataon
        mock_file_body_producer.return_value = dataon
        mock_power_query = self.patch(driver, "power_query")
        mock_power_query.return_value = "on"
        mock_command = self.patch(driver, "command")
        mock_command.return_value = SAMPLE_JSON_HOSTOFF
        mock_set_pxe_boot = self.patch(driver, "set_pxe_boot")

        yield driver.power_on(system_id, context)
        self.assertThat(
            mock_power_query, MockCalledOnceWith(system_id, context)
        )
        self.assertThat(mock_set_pxe_boot, MockCalledWith(context))
        self.assertThat(
            mock_command, MockCalledWith(context, b"PUT", url, dataon)
        )

    @inlineCallbacks
    def test_power_off(self):
        driver = OpenBMCPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        url = driver.get_uri(context, HOST_STATE + "RequestedHostTransition")
        mock_file_body_producer = self.patch(
            openbmc_module, "FileBodyProducer"
        )
        dataoff = FileBodyProducer(
            BytesIO(json.dumps(HOST_OFF).encode("utf-8"))
        )
        mock_openbmc_request = self.patch(driver, "openbmc_request")
        mock_openbmc_request.return_value = dataoff
        mock_file_body_producer.return_value = dataoff
        mock_command = self.patch(driver, "command")
        mock_command.return_value = SAMPLE_JSON_HOSTOFF
        mock_set_pxe_boot = self.patch(driver, "set_pxe_boot")

        yield driver.power_off(system_id, context)
        self.assertThat(mock_set_pxe_boot, MockCalledOnceWith(context))
        self.assertThat(
            mock_command, MockCalledOnceWith(context, b"PUT", url, dataoff)
        )
