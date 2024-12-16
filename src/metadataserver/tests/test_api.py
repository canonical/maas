# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64
from collections import namedtuple
from datetime import datetime, timedelta, timezone
import http.client
from io import BytesIO
import json
from math import ceil, floor
from operator import itemgetter
import os.path
import random
import tarfile
import time
from unittest.mock import ANY, Mock

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.urls import reverse
from netaddr import IPNetwork
from twisted.internet.defer import succeed
import yaml

from maasserver.api import support
from maasserver.enum import NODE_STATUS, NODE_TYPE, NODE_TYPE_CHOICES
from maasserver.exceptions import (
    ClusterUnavailable,
    MAASAPIBadRequest,
    MAASAPINotFound,
    Unauthorized,
)
from maasserver.forms.parameters import ParametersForm
from maasserver.models import (
    Config,
    Event,
    NodeKey,
    NodeMetadata,
    NodeUserData,
    Script,
    ScriptSet,
    SSHKey,
    VersionedTextFile,
)
import maasserver.models.node as node_module
from maasserver.models.node import Node
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.preseed import get_network_yaml_settings
from maasserver.preseed_network import NodeNetworkConfiguration
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.testing.testclient import MAASSensibleOAuthClient
from maasserver.utils.orm import reload_object
from maastesting.utils import sample_binary_data
from metadataserver import api
from metadataserver.api import (
    add_event_to_node_event_log,
    check_version,
    get_node_for_mac,
    get_node_for_request,
    get_queried_node,
    get_script_result_properties,
    make_list_response,
    make_text_response,
    MetaDataHandler,
    NETPLAN_TAR_PATH,
    process_file,
    store_node_power_parameters,
    UnknownMetadataVersion,
)
from metadataserver.builtin_scripts import load_builtin_scripts
from metadataserver.enum import (
    HARDWARE_TYPE,
    RESULT_TYPE,
    SCRIPT_PARALLEL,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
    SCRIPT_STATUS_RUNNING,
    SCRIPT_STATUS_RUNNING_OR_PENDING,
    SCRIPT_TYPE,
    SIGNAL_STATUS,
    SIGNAL_STATUS_CHOICES,
)
from metadataserver.nodeinituser import get_node_init_user
from provisioningserver.enum import POWER_STATE
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_STATUS_MESSAGES,
    EVENT_TYPES,
)
from provisioningserver.refresh.node_info_scripts import (
    LIST_MODALIASES_OUTPUT_NAME,
    NODE_INFO_SCRIPTS,
)
from provisioningserver.utils.network import get_source_address


class TestHelpers(MAASServerTestCase):
    """Tests for the API helper functions."""

    def fake_request(self, **kwargs):
        """Produce a cheap fake request, fresh from the sweat shop.

        Pass as arguments any header items you want to include.
        """
        return namedtuple("FakeRequest", ["headers"])(kwargs)

    def test_make_text_response_presents_text_as_text_plain(self):
        input_text = "Hello."
        response = make_text_response(input_text)
        self.assertEqual("text/plain", response["Content-Type"])
        self.assertEqual(
            input_text, response.content.decode(settings.DEFAULT_CHARSET)
        )

    def test_make_list_response_presents_list_as_newline_separated_text(self):
        response = make_list_response(["aaa", "bbb"])
        self.assertEqual("text/plain", response["Content-Type"])
        self.assertEqual(
            "aaa\nbbb", response.content.decode(settings.DEFAULT_CHARSET)
        )

    def test_check_version_accepts_latest(self):
        check_version("latest")
        # The test is that we get here without exception.

    def test_check_version_reports_unknown_version(self):
        self.assertRaises(UnknownMetadataVersion, check_version, "2.0")

    def test_get_node_for_request_finds_node(self):
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        request = self.fake_request(
            authorization=factory.make_oauth_header(oauth_token=token.key)
        )
        self.assertEqual(node, get_node_for_request(request))

    def test_get_node_for_request_reports_missing_auth_header(self):
        self.assertRaises(
            Unauthorized, get_node_for_request, self.fake_request()
        )

    def test_get_node_for_mac_refuses_if_anonymous_access_disabled(self):
        self.patch(settings, "ALLOW_UNSAFE_METADATA_ACCESS", False)
        self.assertRaises(
            PermissionDenied, get_node_for_mac, factory.make_mac_address()
        )

    def test_get_node_for_mac_raises_404_for_unknown_mac(self):
        self.assertRaises(
            MAASAPINotFound, get_node_for_mac, factory.make_mac_address()
        )

    def test_get_node_for_mac_finds_node_by_mac(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        iface = node.get_boot_interface()
        self.assertEqual(
            iface.node_config.node, get_node_for_mac(iface.mac_address)
        )

    def test_get_queried_node_looks_up_by_mac_if_given(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        iface = node.get_boot_interface()
        self.assertEqual(
            iface.node_config.node,
            get_queried_node(object(), for_mac=iface.mac_address),
        )

    def test_get_queried_node_looks_up_oauth_key_by_default(self):
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        request = self.fake_request(
            authorization=factory.make_oauth_header(oauth_token=token.key)
        )
        self.assertEqual(node, get_queried_node(request))

    def test_add_event_to_node_event_log(self):
        expected_type = {
            # These statuses have specific event types.
            NODE_STATUS.COMMISSIONING: EVENT_TYPES.NODE_COMMISSIONING_EVENT,
            NODE_STATUS.DEPLOYING: EVENT_TYPES.NODE_INSTALL_EVENT,
            # All other statuses generate NODE_STATUS_EVENT events.
            NODE_STATUS.NEW: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.FAILED_COMMISSIONING: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.MISSING: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.READY: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.RESERVED: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.ALLOCATED: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.RETIRED: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.BROKEN: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.FAILED_DEPLOYMENT: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.RELEASING: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.FAILED_RELEASING: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.DISK_ERASING: EVENT_TYPES.NODE_STATUS_EVENT,
            NODE_STATUS.FAILED_DISK_ERASING: EVENT_TYPES.NODE_STATUS_EVENT,
            # Deployed generates different event types.
            NODE_STATUS.DEPLOYED: EVENT_TYPES.NODE_POST_INSTALL_EVENT_FAILED,
            NODE_STATUS.DEPLOYED: EVENT_TYPES.NODE_STATUS_EVENT,
        }

        for status in expected_type:
            node = factory.make_Node(status=status)
            origin = factory.make_name("origin")
            action = factory.make_name("action")
            description = factory.make_name("description")
            add_event_to_node_event_log(
                node, origin, action, description, event_type=""
            )
            event = Event.objects.get(node=node)

            self.assertEqual(node, event.node)
            self.assertEqual(action, event.action)
            self.assertIn(origin, event.description)
            self.assertIn(description, event.description)
            self.assertEqual(expected_type[node.status], event.type.name)

    def test_add_event_to_node_event_log_creates_events_status_messages(self):
        for action in EVENT_STATUS_MESSAGES.keys():
            node = factory.make_Node()
            origin = factory.make_name("origin")
            description = factory.make_name("description")
            add_event_to_node_event_log(
                node, origin, action, description, event_type="start"
            )
            event = Event.objects.filter(node=node).first()

            self.assertEqual(node, event.node)
            self.assertEqual(action, event.action)
            self.assertEqual(
                EVENT_DETAILS[EVENT_STATUS_MESSAGES[action]].description,
                event.type.description,
            )
            self.assertEqual("", event.description)

    def test_add_event_to_node_event_log_logs_rack_refresh(self):
        rack = factory.make_RackController()
        origin = factory.make_name("origin")
        action = factory.make_name("action")
        description = factory.make_name("description")
        add_event_to_node_event_log(rack, origin, action, description, "")
        event = Event.objects.get(node=rack)

        self.assertEqual(rack, event.node)
        self.assertEqual(action, event.action)
        self.assertIn(origin, event.description)
        self.assertIn(description, event.description)
        self.assertEqual(
            EVENT_TYPES.REQUEST_CONTROLLER_REFRESH, event.type.name
        )

    def test_process_file_creates_new_entry_for_output(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        output = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(
            results,
            script_result.script_set,
            script_result.name,
            output,
            request,
        )

        self.assertDictEqual(
            {"exit_status": request["exit_status"], "output": output},
            results[script_result],
        )

    def test_process_file_creates_adds_field_for_output(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        output = factory.make_string()
        stdout = factory.make_string()
        stderr = factory.make_string()
        result = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(
            results,
            script_result.script_set,
            "%s.out" % script_result.name,
            stdout,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.err" % script_result.name,
            stderr,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.yaml" % script_result.name,
            result,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            script_result.name,
            output,
            request,
        )

        self.assertDictEqual(
            {
                "exit_status": request["exit_status"],
                "output": output,
                "stdout": stdout,
                "stderr": stderr,
                "result": result,
            },
            results[script_result],
        )

    def test_process_file_creates_new_entry_for_stdout(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        stdout = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(
            results,
            script_result.script_set,
            "%s.out" % script_result.name,
            stdout,
            request,
        )

        self.assertDictEqual(
            {"exit_status": request["exit_status"], "stdout": stdout},
            results[script_result],
        )

    def test_process_file_creates_adds_field_for_stdout(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        output = factory.make_string()
        stdout = factory.make_string()
        stderr = factory.make_string()
        result = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(
            results,
            script_result.script_set,
            script_result.name,
            output,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.err" % script_result.name,
            stderr,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.yaml" % script_result.name,
            result,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.out" % script_result.name,
            stdout,
            request,
        )

        self.assertDictEqual(
            {
                "exit_status": request["exit_status"],
                "output": output,
                "stdout": stdout,
                "stderr": stderr,
                "result": result,
            },
            results[script_result],
        )

    def test_process_file_creates_new_entry_for_stderr(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        stderr = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(
            results,
            script_result.script_set,
            "%s.err" % script_result.name,
            stderr,
            request,
        )

        self.assertDictEqual(
            {"exit_status": request["exit_status"], "stderr": stderr},
            results[script_result],
        )

    def test_process_file_creates_adds_field_for_stderr(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        output = factory.make_string()
        stdout = factory.make_string()
        stderr = factory.make_string()
        result = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(
            results,
            script_result.script_set,
            script_result.name,
            output,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.out" % script_result.name,
            stdout,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.yaml" % script_result.name,
            result,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.err" % script_result.name,
            stderr,
            request,
        )

        self.assertDictEqual(
            {
                "exit_status": request["exit_status"],
                "output": output,
                "stdout": stdout,
                "stderr": stderr,
                "result": result,
            },
            results[script_result],
        )

    def test_process_file_creates_new_entry_for_result(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        result = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(
            results,
            script_result.script_set,
            "%s.yaml" % script_result.name,
            result,
            request,
        )

        self.assertDictEqual(
            {"exit_status": request["exit_status"], "result": result},
            results[script_result],
        )

    def test_process_file_creates_adds_field_for_result(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        output = factory.make_string()
        stdout = factory.make_string()
        stderr = factory.make_string()
        result = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(
            results,
            script_result.script_set,
            script_result.name,
            output,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.out" % script_result.name,
            stdout,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.err" % script_result.name,
            stderr,
            request,
        )
        process_file(
            results,
            script_result.script_set,
            "%s.yaml" % script_result.name,
            result,
            request,
        )

        self.assertDictEqual(
            {
                "exit_status": request["exit_status"],
                "output": output,
                "stdout": stdout,
                "stderr": stderr,
                "result": result,
            },
            results[script_result],
        )

    def test_process_file_adds_field_for_runtime(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.PENDING)
        result = factory.make_string()
        request = {
            "exit_status": 0,
            "runtime": random.randint(1000, 9999) / 100,
        }

        process_file(
            results,
            script_result.script_set,
            script_result.name,
            result,
            request,
        )

        self.assertDictEqual(
            {
                "exit_status": request["exit_status"],
                "output": result,
                "runtime": request["runtime"],
            },
            results[script_result],
        )

    def test_process_file_finds_script_result_by_id(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        output = factory.make_string()
        request = {
            "exit_status": random.randint(0, 255),
            "script_result_id": script_result.id,
        }

        process_file(
            results,
            script_result.script_set,
            factory.make_name("script_name"),
            output,
            request,
        )

        self.assertDictEqual(
            {"exit_status": request["exit_status"], "output": output},
            results[script_result],
        )

    def test_process_file_adds_script_version_id(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        output = factory.make_string()
        request = {
            "exit_status": random.randint(0, 255),
            "script_result_id": script_result.id,
            "script_version_id": script_result.script.script_id,
        }

        process_file(
            results,
            script_result.script_set,
            factory.make_name("script_name"),
            output,
            request,
        )

        self.assertDictEqual(
            {
                "exit_status": request["exit_status"],
                "output": output,
                "script_version_id": script_result.script.script_id,
            },
            results[script_result],
        )

    def test_creates_new_script_result(self):
        results = {}
        script_name = factory.make_name("script_name")
        script_set = factory.make_ScriptSet()
        output = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(results, script_set, script_name, output, request)
        script_result, value = list(results.items())[0]

        self.assertEqual(script_name, script_result.name)
        self.assertEqual(SCRIPT_STATUS.RUNNING, script_result.status)
        self.assertDictEqual(
            {"exit_status": request["exit_status"], "output": output}, value
        )

    def test_creates_new_script_result_linked_to_script(self):
        results = {}
        script = factory.make_Script()
        script_set = factory.make_ScriptSet()
        output = factory.make_string()
        request = {"exit_status": random.randint(0, 255)}

        process_file(results, script_set, script.name, output, request)
        script_result, value = list(results.items())[0]

        self.assertEqual(script.name, script_result.name)
        self.assertEqual(script_result.script, script)
        self.assertEqual(SCRIPT_STATUS.RUNNING, script_result.status)
        self.assertDictEqual(
            {"exit_status": request["exit_status"], "output": output}, value
        )

    def test_uses_default_exit_status_when_undef(self):
        results = {}
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        output = factory.make_string()
        exit_status = random.randint(0, 255)
        request = {
            "script_result_id": script_result.id,
            "script_version_id": script_result.script.script_id,
        }

        process_file(
            results,
            script_result.script_set,
            factory.make_name("script_name"),
            output,
            request,
            exit_status,
        )

        self.assertDictEqual(
            {
                "exit_status": exit_status,
                "output": output,
                "script_version_id": script_result.script.script_id,
            },
            results[script_result],
        )

    def test_stores_script_version(self):
        results = {}
        script_name = factory.make_name("script_name")
        script = factory.make_Script()
        script.script = script.script.update(factory.make_string())
        script_set = factory.make_ScriptSet()
        output = factory.make_string()
        request = {
            "exit_status": random.randint(0, 255),
            "script_version_id": script.script.id,
        }

        process_file(results, script_set, script_name, output, request)

        script_result, value = list(results.items())[0]

        self.assertEqual(script_name, script_result.name)
        self.assertDictEqual(
            {
                "exit_status": request["exit_status"],
                "output": output,
                "script_version_id": script.script.id,
            },
            value,
        )


def make_node_client(node=None):
    """Create a test client logged in as if it were `node`."""
    if node is None:
        node = factory.make_Node()
    token = NodeKey.objects.get_token_for_node(node)
    return MAASSensibleOAuthClient(get_node_init_user(), token)


def call_signal(
    client=None,
    version="latest",
    files: dict = None,
    headers: dict = None,
    status=None,
    **kwargs,
):
    """Call the API's signal method.

    :param client: Optional client to POST with.  If omitted, will create
        one for a commissioning node.
    :param version: API version to post on.  Defaults to "latest".
    :param files: Optional dict of files to attach.  Maps file name to
        file contents.
    :param **kwargs: Any other keyword parameters are passed on directly
        to the "signal" call.
    """
    if files is None:
        files = {}
    if headers is None:
        headers = {}
    if client is None:
        client = make_node_client(
            factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        )
    if status is None:
        status = SIGNAL_STATUS.OK
    params = {"op": "signal", "status": status}
    params.update(kwargs)
    params.update(
        {
            name: factory.make_file_upload(name, content)
            for name, content in files.items()
        }
    )
    url = reverse("metadata-version", args=[version])
    return client.post(url, params, **headers)


class TestMetadataCommon(MAASServerTestCase):
    """Tests for the common metadata/curtin-metadata API views."""

    # The curtin-metadata and the metadata views are similar in every
    # aspect except the user-data end-point.  The same tests are used to
    # test both end-points.
    scenarios = [
        ("metadata", {"metadata_prefix": "metadata"}),
        ("curtin-metadata", {"metadata_prefix": "curtin-metadata"}),
    ]

    def assertLooksLikeCloudInit(self, actual):
        self.assertTrue(actual.get("cloud-init").startswith("#cloud-config"))

    def get_metadata_name(self, name_suffix=""):
        """Return the Django name of the metadata view.

        :param name_suffix: Suffix of the view name.  The default value is
            the empty string (get_metadata_name() will return the root of
            the metadata API in this case).

        Depending on the value of self.metadata_prefix, this will return
        the name of the metadata view or of the curtin-metadata view.
        """
        return self.metadata_prefix + name_suffix

    def test_no_anonymous_access(self):
        url = reverse(self.get_metadata_name())
        self.assertEqual(
            http.client.UNAUTHORIZED, self.client.get(url).status_code
        )

    def test_metadata_index_shows_latest(self):
        client = make_node_client()
        url = reverse(self.get_metadata_name())
        content = client.get(url).content.decode(settings.DEFAULT_CHARSET)
        self.assertIn("latest", content)

    def test_metadata_index_shows_only_known_versions(self):
        client = make_node_client()
        url = reverse(self.get_metadata_name())
        content = client.get(url).content.decode(settings.DEFAULT_CHARSET)
        for item in content.splitlines():
            check_version(item)
        # The test is that we get here without exception.

    def test_version_index_shows_unconditional_entries(self):
        client = make_node_client()
        view_name = self.get_metadata_name("-version")
        url = reverse(view_name, args=["latest"])
        content = (
            client.get(url)
            .content.decode(settings.DEFAULT_CHARSET)
            .splitlines()
        )
        for needle in ("meta-data", "maas-commissioning-scripts"):
            self.assertIn(needle, content)

    def test_version_index_does_not_show_user_data_if_not_available(self):
        client = make_node_client()
        view_name = self.get_metadata_name("-version")
        url = reverse(view_name, args=["latest"])
        content = client.get(url).content.decode(settings.DEFAULT_CHARSET)
        self.assertNotIn("user-data", content.splitlines())

    def test_version_index_shows_user_data_if_available(self):
        node = factory.make_Node()
        NodeUserData.objects.set_user_data(node, b"User data for node")
        client = make_node_client(node)
        view_name = self.get_metadata_name("-version")
        url = reverse(view_name, args=["latest"])
        content = client.get(url).content.decode(settings.DEFAULT_CHARSET)
        self.assertIn("user-data", content.splitlines())

    def test_meta_data_view_lists_fields(self):
        # Some fields only are returned if there is data related to them.
        user, _ = factory.make_user_with_keys(n_keys=2, username="my-user")
        node = factory.make_Node(owner=user)
        client = make_node_client(node=node)
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", ""])
        response = client.get(url)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertCountEqual(
            MetaDataHandler.subfields,
            [
                field.decode(settings.DEFAULT_CHARSET)
                for field in response.content.split()
            ],
        )

    def test_meta_data_view_is_sorted(self):
        client = make_node_client()
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", ""])
        response = client.get(url)
        attributes = response.content.split()
        self.assertEqual(sorted(attributes), attributes)

    def test_meta_data_unknown_item_is_not_found(self):
        client = make_node_client()
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "UNKNOWN-ITEM"])
        response = client.get(url)
        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_get_attribute_producer_supports_all_fields(self):
        handler = MetaDataHandler()
        producers = list(map(handler.get_attribute_producer, handler.fields))
        self.assertNotIn(None, producers)

    def test_meta_data_local_hostname_returns_fqdn(self):
        hostname = factory.make_string()
        domain = factory.make_Domain()
        node = factory.make_Node(hostname=f"{hostname}.{domain.name}")
        client = make_node_client(node)
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "local-hostname"])
        response = client.get(url)
        self.assertEqual(
            (http.client.OK, node.fqdn),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )
        self.assertIn("text/plain", response["Content-Type"])

    def test_meta_data_instance_id_returns_system_id(self):
        node = factory.make_Node()
        client = make_node_client(node)
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "instance-id"])
        response = client.get(url)
        self.assertEqual(
            (http.client.OK, node.system_id),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )
        self.assertIn("text/plain", response["Content-Type"])

    def test_public_keys_not_listed_for_node_without_public_keys(self):
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", ""])
        client = make_node_client()
        response = client.get(url)
        self.assertNotIn(
            "public-keys",
            response.content.decode(settings.DEFAULT_CHARSET).split("\n"),
        )

    def test_public_keys_not_listed_for_comm_node_with_ssh_disabled(self):
        user, _ = factory.make_user_with_keys(n_keys=2, username="my-user")
        node = factory.make_Node(
            owner=user, status=NODE_STATUS.COMMISSIONING, enable_ssh=False
        )
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", ""])
        client = make_node_client(node=node)
        response = client.get(url)
        self.assertNotIn(
            "public-keys",
            response.content.decode(settings.DEFAULT_CHARSET).split("\n"),
        )

    def test_public_keys_listed_for_comm_node_with_ssh_enabled(self):
        user, _ = factory.make_user_with_keys(n_keys=2, username="my-user")
        node = factory.make_Node(
            owner=user, status=NODE_STATUS.COMMISSIONING, enable_ssh=True
        )
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", ""])
        client = make_node_client(node=node)
        response = client.get(url)
        self.assertIn(
            "public-keys",
            response.content.decode(settings.DEFAULT_CHARSET).split("\n"),
        )

    def test_public_keys_listed_for_node_with_public_keys(self):
        user, _ = factory.make_user_with_keys(n_keys=2, username="my-user")
        node = factory.make_Node(owner=user)
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", ""])
        client = make_node_client(node=node)
        response = client.get(url)
        self.assertIn(
            "public-keys",
            response.content.decode(settings.DEFAULT_CHARSET).split("\n"),
        )

    def test_public_keys_for_node_without_public_keys_returns_empty(self):
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "public-keys"])
        client = make_node_client()
        response = client.get(url)
        self.assertEqual(
            (http.client.OK, b""), (response.status_code, response.content)
        )

    def test_public_keys_for_node_returns_list_of_keys(self):
        user, _ = factory.make_user_with_keys(n_keys=2, username="my-user")
        node = factory.make_Node(owner=user)
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "public-keys"])
        client = make_node_client(node=node)
        response = client.get(url)
        self.assertEqual(http.client.OK, response.status_code)
        keys = SSHKey.objects.filter(user=user).values_list("key", flat=True)
        expected_response = "\n".join(keys)
        self.assertEqual(
            expected_response,
            response.content.decode(settings.DEFAULT_CHARSET),
        )
        self.assertIn("text/plain", response["Content-Type"])

    def test_public_keys_url_with_additional_slashes(self):
        # The metadata service also accepts urls with any number of additional
        # slashes after 'metadata': e.g. http://host/metadata///rest-of-url.
        user, _ = factory.make_user_with_keys(n_keys=2, username="my-user")
        node = factory.make_Node(owner=user)
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "public-keys"])
        # Insert additional slashes.
        url = url.replace("metadata", "metadata/////")
        client = make_node_client(node=node)
        response = client.get(url)
        keys = SSHKey.objects.filter(user=user).values_list("key", flat=True)
        self.assertEqual(
            "\n".join(keys),
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_vendor_data_publishes_yaml(self):
        node = factory.make_Node()
        client = make_node_client(node)
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "vendor-data"])
        response = client.get(url)
        self.assertEqual(
            "application/x-yaml; charset=utf-8",
            response.get("Content-Type"),
        )

    def test_vendor_data_node_with_owner_def_user_includes_system_info(self):
        # Test vendor_data includes system_info when the node has an owner
        # and a default_user set.
        user, _ = factory.make_user_with_keys(n_keys=2, username="my-user")
        node = factory.make_Node(owner=user, default_user=user)
        client = make_node_client(node)
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "vendor-data"])
        response = client.get(url)
        content = yaml.safe_load(response.content)
        self.assertEqual(response.status_code, http.client.OK)
        self.assertLooksLikeCloudInit(content)
        self.assertCountEqual(
            yaml.safe_load(content["cloud-init"]),
            ["runcmd", "snap", "system_info"],
        )

    def test_vendor_data_node_without_def_user_includes_no_system_info(self):
        # Test vendor_data includes no system_info when the node has an owner
        # but doesn't have a default_user set.
        user, _ = factory.make_user_with_keys(n_keys=2, username="my-user")
        node = factory.make_Node(owner=user)
        client = make_node_client(node)
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "vendor-data"])
        response = client.get(url)
        content = yaml.safe_load(response.content)
        self.assertEqual(response.status_code, http.client.OK)
        self.assertLooksLikeCloudInit(content)
        self.assertCountEqual(
            yaml.safe_load(content["cloud-init"]),
            ["runcmd", "snap"],
        )

    def test_vendor_data_for_node_without_owner_includes_no_system_info(self):
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "vendor-data"])
        client = make_node_client()
        response = client.get(url)
        content = yaml.safe_load(response.content)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertLooksLikeCloudInit(content)
        self.assertCountEqual(
            yaml.safe_load(content["cloud-init"]),
            ["runcmd", "snap"],
        )

    def test_vendor_data_calls_through_to_get_vendor_data(self):
        # i.e. for further information, see `get_vendor_data`.
        get_vendor_data = self.patch_autospec(api, "get_vendor_data")
        get_vendor_data.return_value = {"foo": factory.make_name("bar")}
        view_name = self.get_metadata_name("-meta-data")
        url = reverse(view_name, args=["latest", "vendor-data"])
        node = factory.make_Node()
        client = make_node_client(node)
        response = client.get(url)
        content = yaml.safe_load(response.content)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertLooksLikeCloudInit(content)
        self.assertEqual(
            get_vendor_data.return_value,
            yaml.safe_load(content["cloud-init"]),
        )
        get_vendor_data.assert_called_once_with(node, ANY)


class TestMetadataUserData(MAASServerTestCase):
    """Tests for the metadata user-data API endpoint."""

    def test_user_data_view_returns_binary_data_and_creates_sts_msg(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        NodeUserData.objects.set_user_data(node, sample_binary_data)
        client = make_node_client(node)
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        event = Event.objects.last()
        self.assertEqual("application/octet-stream", response["Content-Type"])
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.OK, sample_binary_data),
            (response.status_code, response.content),
        )
        self.assertEqual(event.type.name, EVENT_TYPES.GATHERING_INFO)

    def test_poweroff_user_data_returned_if_unexpected_status(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        NodeUserData.objects.set_user_data(node, sample_binary_data)
        client = make_node_client(node)
        user_data = factory.make_name("user data").encode("ascii")
        self.patch(api, "generate_user_data_for_poweroff").return_value = (
            user_data
        )
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        self.assertEqual("application/octet-stream", response["Content-Type"])
        self.assertIsInstance(response.content, bytes)
        self.assertEqual(
            (http.client.OK, user_data),
            (response.status_code, response.content),
        )

    def test_user_data_for_node_without_user_data_returns_not_found(self):
        client = make_node_client(
            factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        )
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        self.assertEqual(http.client.NOT_FOUND, response.status_code)


class TestMetadataUserDataStateChanges(MAASServerTestCase):
    """Tests for the metadata user-data API endpoint."""

    def setUp(self):
        super().setUp()
        self.useFixture(SignalsDisabled("power"))

    def test_request_does_not_cause_status_change_if_not_deploying(self):
        status = factory.pick_enum(
            NODE_STATUS, but_not=[NODE_STATUS.DEPLOYING]
        )
        node = factory.make_Node(status=status)
        NodeUserData.objects.set_user_data(node, sample_binary_data)
        client = make_node_client(node)
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(status, reload_object(node).status)

    def test_request_causes_status_change_if_deploying(self):
        signal_workflow = self.patch(node_module, "signal_workflow")
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        NodeUserData.objects.set_user_data(node, sample_binary_data)
        client = make_node_client(node)
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)
        signal_workflow.assert_called_with(
            f"deploy:{node.system_id}", "deployed-os-ready"
        )

    def test_skips_status_change_if_installing_kvm_and_sets_agent_name(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, install_kvm=True
        )
        NodeUserData.objects.set_user_data(node, sample_binary_data)
        client = make_node_client(node)
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)
        node = reload_object(node)
        self.assertEqual(node.agent_name, "maas-kvm-pod")

    def test_skips_status_change_if_registering_vmhost_and_sets_agent_name(
        self,
    ):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, register_vmhost=True
        )
        NodeUserData.objects.set_user_data(node, sample_binary_data)
        client = make_node_client(node)
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)
        node = reload_object(node)
        self.assertEqual(node.agent_name, "maas-kvm-pod")

    def test_returns_plain_text_user_data_when_uploaded_as_plain_text(self):
        signal_workflow = self.patch(node_module, "signal_workflow")
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        user_data = factory.make_name("user_data").encode()
        NodeUserData.objects.set_user_data(node, user_data)
        client = make_node_client(node)
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)
        self.assertEqual(user_data, response.content)
        signal_workflow.assert_called_with(
            f"deploy:{node.system_id}", "deployed-os-ready"
        )

    def test_returns_plain_text_user_data_when_uploaded_as_b64(self):
        signal_workflow = self.patch(node_module, "signal_workflow")
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        user_data = factory.make_name("user_data").encode()
        NodeUserData.objects.set_user_data(node, base64.b64encode(user_data))
        client = make_node_client(node)
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)
        self.assertEqual(user_data, response.content)
        signal_workflow.assert_called_with(
            f"deploy:{node.system_id}", "deployed-os-ready"
        )

    def test_returns_plain_text_user_data_when_uploaded_as_b64_with_nl(self):
        signal_workflow = self.patch(node_module, "signal_workflow")
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        user_data = factory.make_name("user_data").encode()
        b64_user_data = base64.b64encode(user_data).decode()
        mid = len(b64_user_data) // 2
        b64_user_data = b64_user_data[:mid] + "\n" + b64_user_data[mid:]
        NodeUserData.objects.set_user_data(node, b64_user_data.encode())
        client = make_node_client(node)
        response = client.get(reverse("metadata-user-data", args=["latest"]))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)
        self.assertEqual(user_data, response.content)
        signal_workflow.assert_called_with(
            f"deploy:{node.system_id}", "deployed-os-ready"
        )


class TestCurtinMetadataUserData(MAASServerTestCase):
    """Tests for the curtin-metadata user-data API endpoint."""

    def test_curtin_user_data_view_returns_curtin_data(self):
        # This should be in a reusable place - when we just run this
        # test, it takes ~1s to calculate the API description.
        self.patch(support, "get_api_description").return_value = {
            "hash": "0xDEADBEEF"
        }
        node = factory.make_Node()
        url = reverse("curtin-metadata-user-data", args=["latest"])
        userdata = self.patch(api, "get_curtin_userdata")
        client = make_node_client(node)

        response = client.get(url)
        userdata.assert_called_once_with(ANY, node)
        self.assertEqual(
            http.client.OK.value, response.status_code, response.content
        )


class TestInstallingAPI(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.patch(node_module, "stop_workflow")
        self.useFixture(SignalsDisabled("power"))

    def test_other_user_than_node_cannot_signal_installation_result(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        client = MAASSensibleOAuthClient(factory.make_User())
        response = call_signal(client)
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test_signaling_installation_result_does_not_affect_other_node(self):
        other_node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, with_empty_script_sets=True
        )
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, with_empty_script_sets=True
        )
        client = make_node_client(node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.DEPLOYING, reload_object(other_node).status
        )

    def test_signaling_installation_success_leaves_node_deploying(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYING,
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test_signaling_installation_success_does_not_populate_tags(self):
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node"
        )
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYING,
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)
        populate_tags_for_single_node.assert_not_called()

    def test_tag_population_failure_logs_event(self):
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node"
        )
        populate_tags_for_single_node.side_effect = Exception
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.COMMISSIONING,
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)
        expected_event = Event.objects.first()
        self.assertIn(
            "Failed to update tags.",
            expected_event.description,
        )

    def test_signaling_installation_success_is_idempotent(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        call_signal(client, status=SIGNAL_STATUS.OK)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test_signaling_installation_success_does_not_clear_owner(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(node.owner, reload_object(node).owner)

    def test_signaling_installation_failure_makes_node_failed(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.FAILED)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DEPLOYMENT, reload_object(node).status
        )

    def test_signaling_installation_failure_is_idempotent(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        call_signal(client, status=SIGNAL_STATUS.FAILED)
        response = call_signal(client, status=SIGNAL_STATUS.FAILED)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DEPLOYMENT, reload_object(node).status
        )

    def test_signaling_installation_updates_last_ping(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.WORKING)
        self.assertEqual(response.status_code, http.client.OK)

        end_time = ceil(time.time())
        script_set = node.current_installation_script_set
        self.assertGreaterEqual(
            ceil(script_set.last_ping.timestamp()), start_time
        )
        self.assertLessEqual(floor(script_set.last_ping.timestamp()), end_time)

    def test_signaling_installation_with_netconf_sets_script_to_netconf(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_installation_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.APPLYING_NETCONF,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.APPLYING_NETCONF, script_result.status)

    def test_signaling_installation_with_install_sets_script_to_install(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_installation_script_set.scriptresult_set.first()
        )
        script_result.status = random.choice(
            [SCRIPT_STATUS.PENDING, SCRIPT_STATUS.APPLYING_NETCONF]
        )
        script_result.save()
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.INSTALLING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.INSTALLING, script_result.status)

    def test_signaling_installation_with_script_id_sets_script_to_run(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_installation_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.RUNNING, script_result.status)

    def test_signaling_installation_with_script_name_sets_script_to_run(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_installation_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            name=script_result.name,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.RUNNING, script_result.status)

    def test_signaling_netconf_with_script_id_ignores_not_pending(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_installation_script_set.scriptresult_set.first()
        )
        script_status = factory.pick_choice(
            SCRIPT_STATUS_CHOICES,
            but_not=[
                SCRIPT_STATUS.PENDING,
                SCRIPT_STATUS.INSTALLING,
                SCRIPT_STATUS.APPLYING_NETCONF,
            ],
        )
        script_result.status = script_status
        script_result.save()
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(script_status, script_result.status)

    def test_signaling_installation_with_script_id_ignores_not_pending(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_installation_script_set.scriptresult_set.first()
        )
        script_status = factory.pick_choice(
            SCRIPT_STATUS_CHOICES,
            but_not=[
                SCRIPT_STATUS.PENDING,
                SCRIPT_STATUS.APPLYING_NETCONF,
                SCRIPT_STATUS.INSTALLING,
            ],
        )
        script_result.status = script_status
        script_result.save()
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(script_status, script_result.status)

    def test_signaling_store_results_updates_hw_sync_last_sync(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            owner=factory.make_User(),
            enable_hw_sync=True,
            with_empty_script_sets=True,
        )
        old_last_sync = node.last_sync = datetime.now(timezone.utc)
        node.save()

        script_result = (
            node.current_installation_script_set.scriptresult_set.first()
        )
        script_status = factory.pick_choice(
            SCRIPT_STATUS_CHOICES,
            but_not=[
                SCRIPT_STATUS.PENDING,
                SCRIPT_STATUS.APPLYING_NETCONF,
                SCRIPT_STATUS.INSTALLING,
            ],
        )
        script_result.status = script_status
        script_result.save()
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)
        node.refresh_from_db()
        self.assertGreater(node.last_sync, old_last_sync)


class TestMAASScripts(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        load_builtin_scripts()

    def extract_and_validate_file(
        self, tar, path, start_time, end_time, content, mode=0o755
    ):
        member = tar.getmember(path)
        self.assertGreaterEqual(member.mtime, start_time)
        self.assertLessEqual(member.mtime, end_time)
        self.assertEqual(mode, member.mode)
        self.assertEqual(content, tar.extractfile(path).read())

    def validate_scripts(
        self, script_set, path_name, tar, start_time, end_time
    ):
        meta_data = []
        contains_network_config = False
        for script_result in script_set:
            script_path = os.path.join(path_name, script_result.name)
            md_item = {
                "name": script_result.name,
                "path": script_path,
                "script_result_id": script_result.id,
            }
            if script_result.script is None:
                script = NODE_INFO_SCRIPTS[script_result.name]
                content = script["content"]
                md_item["timeout_seconds"] = script["timeout"].total_seconds()
                md_item["parallel"] = script.get(
                    "parallel", SCRIPT_PARALLEL.DISABLED
                )
                md_item["hardware_type"] = script.get(
                    "hardware_type", HARDWARE_TYPE.NODE
                )
                md_item["packages"] = script.get("packages", {})
                md_item["for_hardware"] = script.get("for_hardware", [])
                md_item["apply_configured_networking"] = script.get(
                    "apply_configured_networking", False
                )
            else:
                content = script_result.script.script.data.encode()
                md_item["script_version_id"] = script_result.script.script.id
                md_item["timeout_seconds"] = (
                    script_result.script.timeout.total_seconds()
                )
                md_item["parallel"] = script_result.script.parallel
                md_item["hardware_type"] = script_result.script.hardware_type
                md_item["parameters"] = script_result.parameters
                md_item["packages"] = script_result.script.packages
                md_item["for_hardware"] = script_result.script.for_hardware
                md_item["apply_configured_networking"] = (
                    script_result.script.apply_configured_networking
                )

            md_item["has_finished"] = (
                script_result.status not in SCRIPT_STATUS_RUNNING_OR_PENDING
            )
            if script_result.status == SCRIPT_STATUS.PENDING:
                md_item["has_started"] = False
            else:
                md_item["has_started"] = True
                out_path = os.path.join(
                    "out", f"{script_result.name}.{script_result.id}"
                )
                self.extract_and_validate_file(
                    tar, out_path, start_time, end_time, script_result.output
                )
                self.extract_and_validate_file(
                    tar,
                    "%s.out" % out_path,
                    start_time,
                    end_time,
                    script_result.stdout,
                )
                self.extract_and_validate_file(
                    tar,
                    "%s.err" % out_path,
                    start_time,
                    end_time,
                    script_result.stderr,
                )
                self.extract_and_validate_file(
                    tar,
                    "%s.yaml" % out_path,
                    start_time,
                    end_time,
                    script_result.result,
                )
            md_item["default"] = script_result.script.default
            md_item["tags"] = script_result.script.tags

            if md_item["apply_configured_networking"]:
                contains_network_config = True

            self.extract_and_validate_file(
                tar, script_path, start_time, end_time, content
            )
            meta_data.append(md_item)

        if contains_network_config:
            node = script_result.script_set.node
            configs = Config.objects.get_configs(
                ["commissioning_osystem", "commissioning_distro_series"]
            )
            network_yaml_settings = get_network_yaml_settings(
                configs["commissioning_osystem"],
                configs["commissioning_distro_series"],
            )
            network_config = NodeNetworkConfiguration(
                node,
                version=network_yaml_settings.version,
                source_routing=network_yaml_settings.source_routing,
            )
            network_config_yaml = yaml.safe_dump(
                network_config.config, default_flow_style=False
            )
            self.extract_and_validate_file(
                tar,
                NETPLAN_TAR_PATH,
                start_time,
                end_time,
                network_config_yaml.encode(),
                0o644,
            )
        else:
            self.assertNotIn(NETPLAN_TAR_PATH, tar.getnames())
        return meta_data

    def test_anon_access_returns_commissioning_scripts(self):
        # Simulate user uploaded commissioning script
        factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
        start_time = floor(time.time())
        response = self.client.get(reverse("maas-scripts", args=["latest"]))
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # The + 1 is for the index.json file.
        self.assertEqual(len(NODE_INFO_SCRIPTS) + 1, len(tar.getmembers()))
        commissioning_meta_data = []
        for script in (
            Script.objects.filter(
                script_type=SCRIPT_TYPE.COMMISSIONING, default=True
            )
            .exclude(
                # Network configuration is based on node configuration however
                # the node doesn't exist yet. Once the node is created the
                # client will rerequest the NodeScripts tar which may include
                # scripts which test networking.
                apply_configured_networking=True
            )
            .order_by("name")
        ):
            form = ParametersForm(data={}, script=script, node=Node())
            self.assertTrue(form.is_valid(), form.errors)
            path = os.path.join("commissioning", script.name)
            for parameters in form.cleaned_data["input"]:
                commissioning_meta_data.append(
                    {
                        "name": script.name,
                        "path": path,
                        "script_version_id": script.script.id,
                        "timeout_seconds": script.timeout.total_seconds(),
                        "parallel": script.parallel,
                        "hardware_type": script.hardware_type,
                        "parameters": parameters,
                        "packages": script.packages,
                        "for_hardware": script.for_hardware,
                        "apply_configured_networking": script.apply_configured_networking,
                    }
                )
            self.extract_and_validate_file(
                tar, path, start_time, end_time, script.script.data.encode()
            )
        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertEqual(
            {
                "1.0": {
                    "commissioning_scripts": sorted(
                        commissioning_meta_data, key=itemgetter("name")
                    )
                }
            },
            meta_data,
        )

    def test_anon_returns_bmc_config_scripts_when_disabled(self):
        Config.objects.set_config("enlist_commissioning", False)
        start_time = floor(time.time())
        response = self.client.get(reverse("maas-scripts", args=["latest"]))
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        self.assertEqual(2, len(tar.getmembers()))
        commissioning_meta_data = []
        for script in (
            Script.objects.filter(script_type=SCRIPT_TYPE.COMMISSIONING)
            .filter(tags__overlap=["bmc-config"])
            .order_by("name")
        ):
            form = ParametersForm(data={}, script=script, node=Node())
            self.assertTrue(form.is_valid(), form.errors)
            path = os.path.join("commissioning", script.name)
            for parameters in form.cleaned_data["input"]:
                commissioning_meta_data.append(
                    {
                        "name": script.name,
                        "path": path,
                        "script_version_id": script.script.id,
                        "timeout_seconds": script.timeout.total_seconds(),
                        "parallel": script.parallel,
                        "hardware_type": script.hardware_type,
                        "parameters": parameters,
                        "packages": script.packages,
                        "for_hardware": script.for_hardware,
                        "apply_configured_networking": script.apply_configured_networking,
                    }
                )
            self.extract_and_validate_file(
                tar, path, start_time, end_time, script.script.data.encode()
            )
        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertEqual(
            {
                "1.0": {
                    "commissioning_scripts": sorted(
                        commissioning_meta_data, key=itemgetter("name")
                    )
                }
            },
            meta_data,
        )

    def test_anon_access_returns_custom_enlist_script(self):
        enlistment_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            tags=["enlisting"],
            parameters={
                "string": {
                    "type": "string",
                    "default": factory.make_name("default"),
                }
            },
        )
        start_time = floor(time.time())
        response = self.client.get(reverse("maas-scripts", args=["latest"]))
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # The + 2 is for the index.json file and the custom enlistment script.
        self.assertEqual(len(NODE_INFO_SCRIPTS) + 2, len(tar.getmembers()))
        commissioning_meta_data = []
        for script in (
            Script.objects.filter(script_type=SCRIPT_TYPE.COMMISSIONING)
            .filter(Q(default=True) | Q(name=enlistment_script.name))
            .exclude(
                # Network configuration is based on node configuration however
                # the node doesn't exist yet. Once the node is created the
                # client will rerequest the NodeScripts tar which may include
                # scripts which test networking.
                apply_configured_networking=True
            )
            .order_by("name")
        ):
            form = ParametersForm(data={}, script=script, node=Node())
            self.assertTrue(form.is_valid(), form.errors)
            path = os.path.join("commissioning", script.name)
            for parameters in form.cleaned_data["input"]:
                commissioning_meta_data.append(
                    {
                        "name": script.name,
                        "path": path,
                        "script_version_id": script.script.id,
                        "timeout_seconds": script.timeout.total_seconds(),
                        "parallel": script.parallel,
                        "hardware_type": script.hardware_type,
                        "parameters": parameters,
                        "packages": script.packages,
                        "for_hardware": script.for_hardware,
                        "apply_configured_networking": script.apply_configured_networking,
                    }
                )
            self.extract_and_validate_file(
                tar, path, start_time, end_time, script.script.data.encode()
            )
        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertEqual(
            {
                "1.0": {
                    "commissioning_scripts": sorted(
                        commissioning_meta_data, key=itemgetter("name")
                    )
                }
            },
            meta_data,
        )

    def test_returns_all_scripts_when_commissioning(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # The + 1 is for the index.json file.
        self.assertEqual(
            node.current_commissioning_script_set.scriptresult_set.count()
            + node.current_testing_script_set.scriptresult_set.count()
            + 1,
            len(tar.getmembers()),
        )

        commissioning_meta_data = self.validate_scripts(
            node.current_commissioning_script_set,
            "commissioning",
            tar,
            start_time,
            end_time,
        )
        testing_meta_data = self.validate_scripts(
            node.current_testing_script_set,
            "testing",
            tar,
            start_time,
            end_time,
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertDictEqual(
            {
                "1.0": {
                    "commissioning_scripts": sorted(
                        commissioning_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    ),
                    "testing_scripts": sorted(
                        testing_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    ),
                }
            },
            meta_data,
        )

    def test_adds_for_hardware_scripts_when_commissioning_on_second_req(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        commissioning_script_set = node.current_commissioning_script_set
        testing_script_set = node.current_testing_script_set
        # Subtract one as modalias will no longer be returned due to it
        # finishing.
        orig_script_count = (
            commissioning_script_set.scriptresult_set.count()
            + testing_script_set.scriptresult_set.count()
            - 1
        )
        modalias_script_result = commissioning_script_set.find_script_result(
            script_name=LIST_MODALIASES_OUTPUT_NAME
        )
        modalias_script_result.store_result(
            exit_status=0,
            stdout=b"pci:v00008086d00001918sv000015D9sd00000888bc06sc00i00",
        )
        for_hardware_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            for_hardware=["pci:8086:1918"],
        )
        commissioning_script_set.tags = for_hardware_script.tags
        commissioning_script_set.save()
        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        # The + 2 is for the index.json file and the for_hardware script.
        self.assertEqual(orig_script_count + 2, len(tar.getmembers()))
        self.assertEqual(
            for_hardware_script,
            commissioning_script_set.scriptresult_set.get(
                script=for_hardware_script
            ).script,
        )

    def test_returns_testing_scripts_when_testing(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.TESTING, with_empty_script_sets=True
        )

        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # The + 1 is for the index.json file.
        self.assertEqual(
            node.current_testing_script_set.scriptresult_set.count() + 1,
            len(tar.getmembers()),
        )

        testing_meta_data = self.validate_scripts(
            node.current_testing_script_set,
            "testing",
            tar,
            start_time,
            end_time,
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertDictEqual(
            {
                "1.0": {
                    "testing_scripts": sorted(
                        testing_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    )
                }
            },
            meta_data,
        )

    def test_returns_commissioning_scripts_when_entering_rescue_mode(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.ENTERING_RESCUE_MODE,
            with_empty_script_sets=True,
        )
        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # The + 1 is for the index.json file.
        self.assertEqual(
            node.current_commissioning_script_set.scriptresult_set.count()
            + node.current_testing_script_set.scriptresult_set.count()
            + 1,
            len(tar.getmembers()),
        )

        commissioning_meta_data = self.validate_scripts(
            node.current_commissioning_script_set,
            "commissioning",
            tar,
            start_time,
            end_time,
        )
        testing_meta_data = self.validate_scripts(
            node.current_testing_script_set,
            "testing",
            tar,
            start_time,
            end_time,
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertDictEqual(
            {
                "1.0": {
                    "commissioning_scripts": sorted(
                        commissioning_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    ),
                    "testing_scripts": sorted(
                        testing_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    ),
                }
            },
            meta_data,
        )

    def test_returns_commissioning_scripts_when_in_rescue_mode(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.RESCUE_MODE, with_empty_script_sets=True
        )
        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # The + 1 is for the index.json file.
        self.assertEqual(
            node.current_commissioning_script_set.scriptresult_set.count()
            + node.current_testing_script_set.scriptresult_set.count()
            + 1,
            len(tar.getmembers()),
        )

        commissioning_meta_data = self.validate_scripts(
            node.current_commissioning_script_set,
            "commissioning",
            tar,
            start_time,
            end_time,
        )
        testing_meta_data = self.validate_scripts(
            node.current_testing_script_set,
            "testing",
            tar,
            start_time,
            end_time,
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertDictEqual(
            {
                "1.0": {
                    "commissioning_scripts": sorted(
                        commissioning_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    ),
                    "testing_scripts": sorted(
                        testing_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    ),
                }
            },
            meta_data,
        )

    def test_returns_finished_scripts_when_deployed(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, with_empty_script_sets=True
        )
        node.current_commissioning_script_set.scriptresult_set.all().update(
            status=SCRIPT_STATUS.PASSED
        )
        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        commissioning_scripts = {
            name.split("/", 1)[-1]
            for name in tar.getnames()
            if name.startswith("commissioning/")
        }
        self.assertEqual(NODE_INFO_SCRIPTS.keys(), commissioning_scripts)

        end_time = ceil(time.time())

        commissioning_meta_data = self.validate_scripts(
            node.current_commissioning_script_set,
            "commissioning",
            tar,
            start_time,
            end_time,
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertCountEqual(
            commissioning_meta_data,
            meta_data["1.0"]["commissioning_scripts"],
        )

    def test_removes_scriptless_script_result(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING, with_empty_script_sets=True
        )

        bad_script_result = (
            node.current_testing_script_set.scriptresult_set.first()
        )
        bad_script_result.script.delete()
        script_result = factory.make_ScriptResult(
            script_set=node.current_testing_script_set,
            status=SCRIPT_STATUS.PENDING,
        )

        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        self.assertEqual(2, len(tar.getmembers()))

        self.assertEqual(
            1, node.current_testing_script_set.scriptresult_set.count()
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertDictEqual(
            {
                "1.0": {
                    "testing_scripts": [
                        {
                            "name": script_result.name,
                            "path": os.path.join(
                                "testing", script_result.name
                            ),
                            "script_result_id": script_result.id,
                            "script_version_id": script_result.script.script.id,
                            "timeout_seconds": (
                                script_result.script.timeout.total_seconds()
                            ),
                            "parallel": script_result.script.parallel,
                            "hardware_type": script_result.script.hardware_type,
                            "parameters": script_result.parameters,
                            "packages": script_result.script.packages,
                            "for_hardware": script_result.script.for_hardware,
                            "apply_configured_networking": (
                                script_result.script.apply_configured_networking
                            ),
                            "has_started": False,
                            "has_finished": False,
                            "default": False,
                            "tags": script_result.script.tags,
                        }
                    ]
                }
            },
            meta_data,
        )

    def test_only_returns_scripts_which_havnt_been_run(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )

        script = factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
        already_run_commissioning_script = factory.make_ScriptResult(
            script_set=node.current_commissioning_script_set,
            script=script,
            status=SCRIPT_STATUS.PASSED,
        )
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        already_run_testing_script = factory.make_ScriptResult(
            script_set=node.current_testing_script_set,
            script=script,
            status=SCRIPT_STATUS.FAILED,
        )

        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # We have two scripts which have been run but the tar always includes
        # an index.json file so subtract one.
        self.assertEqual(
            node.current_commissioning_script_set.scriptresult_set.count()
            + node.current_testing_script_set.scriptresult_set.count()
            - 1,
            len(tar.getmembers()),
        )

        commissioning_meta_data = self.validate_scripts(
            [
                script_result
                for script_result in node.current_commissioning_script_set
                if script_result.id != already_run_commissioning_script.id
            ],
            "commissioning",
            tar,
            start_time,
            end_time,
        )
        testing_meta_data = self.validate_scripts(
            [
                script_result
                for script_result in node.current_testing_script_set
                if script_result.id != already_run_testing_script.id
            ],
            "testing",
            tar,
            start_time,
            end_time,
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertDictEqual(
            {
                "1.0": {
                    "commissioning_scripts": sorted(
                        commissioning_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    ),
                    "testing_scripts": sorted(
                        testing_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    ),
                }
            },
            meta_data,
        )

    def test_returns_output_when_has_started(self):
        start_time = floor(time.time())
        node = factory.make_Node(status=NODE_STATUS.TESTING)
        script_set = factory.make_ScriptSet(result_type=RESULT_TYPE.TESTING)
        node.current_testing_script_set = script_set
        node.save()
        factory.make_ScriptResult(
            script_set=script_set, status=SCRIPT_STATUS.RUNNING
        )

        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # index.json + one script + combined, stdout, stderr, and result
        # output.
        self.assertEqual(6, len(tar.getmembers()))

        testing_meta_data = self.validate_scripts(
            node.current_testing_script_set,
            "testing",
            tar,
            start_time,
            end_time,
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertDictEqual(
            {
                "1.0": {
                    "testing_scripts": sorted(
                        testing_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    )
                }
            },
            meta_data,
        )

    def test_contains_netplan_yaml_with_apply_config_networking(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            osystem=factory.make_name("osystem"),
            distro_series=factory.make_name("distro_series"),
        )
        script_set = factory.make_ScriptSet(result_type=RESULT_TYPE.TESTING)
        node.current_testing_script_set = script_set
        node.save()
        script = factory.make_Script(apply_configured_networking=True)
        factory.make_ScriptResult(
            script=script, script_set=script_set, status=SCRIPT_STATUS.PENDING
        )

        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # index.json + one script + netplan.yaml
        self.assertEqual(3, len(tar.getmembers()))

        testing_meta_data = self.validate_scripts(
            node.current_testing_script_set,
            "testing",
            tar,
            start_time,
            end_time,
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        self.assertDictEqual(
            {
                "1.0": {
                    "testing_scripts": sorted(
                        testing_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    )
                }
            },
            meta_data,
        )

    def test_returns_no_content_when_no_scripts(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.NO_CONTENT,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )

    def test_scripts_with_timeout_greater_than_24_hours(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.TESTING, with_empty_script_sets=True
        )
        # Make script timeout value to 24:05:00
        timeout = timedelta(days=1, seconds=600)
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, timeout=timeout
        )
        factory.make_ScriptResult(
            script_set=node.current_testing_script_set,
            script=script,
            status=SCRIPT_STATUS.PENDING,
        )
        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )

        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())

        testing_meta_data = self.validate_scripts(
            node.current_testing_script_set,
            "testing",
            tar,
            start_time,
            end_time,
        )
        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )
        # Assertion should fail if timeout conversions are improper
        self.assertDictEqual(
            {
                "1.0": {
                    "testing_scripts": sorted(
                        testing_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    ),
                }
            },
            meta_data,
        )

    def _test_release_scripts_are_returned(self, node_status: NODE_STATUS):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=node_status, with_empty_script_sets=True
        )

        script = factory.make_Script(script_type=SCRIPT_TYPE.RELEASE)
        factory.make_ScriptResult(
            script_set=node.current_release_script_set,
            script=script,
            status=SCRIPT_STATUS.PENDING,
        )

        response = make_node_client(node=node).get(
            reverse("maas-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertEqual("application/x-tar", response["Content-Type"])
        tar = tarfile.open(mode="r", fileobj=BytesIO(response.content))
        end_time = ceil(time.time())
        # The + 1 is for the index.json file.
        self.assertEqual(
            node.current_release_script_set.scriptresult_set.count() + 1,
            len(tar.getmembers()),
        )

        release_meta_data = self.validate_scripts(
            node.current_release_script_set,
            "release",
            tar,
            start_time,
            end_time,
        )

        meta_data = json.loads(
            tar.extractfile("index.json").read().decode("utf-8")
        )

        self.assertDictEqual(
            {
                "1.0": {
                    "release_scripts": sorted(
                        release_meta_data,
                        key=itemgetter("name", "script_result_id"),
                    )
                }
            },
            meta_data,
        )

    def test_returns_release_scripts_when_releasing(self):
        self._test_release_scripts_are_returned(NODE_STATUS.RELEASING)

    def test_returns_release_scripts_when_erasing_disks(self):
        self._test_release_scripts_are_returned(NODE_STATUS.DISK_ERASING)


class TestMAASScriptsProperties(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        load_builtin_scripts()

    def test_script_pending(self):
        result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PENDING,
        )
        properties = get_script_result_properties(result)
        self.assertFalse(properties["has_started"])
        self.assertFalse(properties["has_finished"])

    def test_script_running(self):
        result = factory.make_ScriptResult(
            status=random.choice(list(SCRIPT_STATUS_RUNNING)),
        )
        properties = get_script_result_properties(result)
        self.assertTrue(properties["has_started"])
        self.assertFalse(properties["has_finished"])

    def test_script_finished(self):
        result = factory.make_ScriptResult(
            status=factory.pick_choice(
                SCRIPT_STATUS_CHOICES,
                but_not=SCRIPT_STATUS_RUNNING_OR_PENDING,
            ),
        )
        properties = get_script_result_properties(result)
        self.assertTrue(properties["has_started"])
        self.assertTrue(properties["has_finished"])

    def test_script_default(self):
        builtin_scriptresult = factory.make_ScriptResult(
            script=random.choice(Script.objects.filter(default=True).all()),
        )
        user_scriptresult = factory.make_ScriptResult()
        builtin_properties = get_script_result_properties(builtin_scriptresult)
        user_properties = get_script_result_properties(user_scriptresult)
        self.assertTrue(builtin_properties["default"])
        self.assertFalse(user_properties["default"])

    def test_script_tags(self):
        tags_scriptresult = factory.make_ScriptResult(
            script=factory.make_Script(
                tags=["foo", "bar"], hardware_type=HARDWARE_TYPE.NODE
            )
        )
        notags_scriptresult = factory.make_ScriptResult(
            script=factory.make_Script(
                tags=[], hardware_type=HARDWARE_TYPE.STORAGE
            )
        )
        tags_properties = get_script_result_properties(tags_scriptresult)
        notags_properties = get_script_result_properties(notags_scriptresult)
        self.assertEqual(["foo", "bar", "node"], tags_properties["tags"])
        # There is always a tag, since the hardware type gets added as
        # an implicit tag.
        self.assertEqual(["storage"], notags_properties["tags"])


class TestCommissioningAPI(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(SignalsDisabled("power"))

    def test_commissioning_scripts(self):
        load_builtin_scripts()
        start_time = floor(time.time())
        # Create custom commissioing scripts
        binary_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            script=VersionedTextFile.objects.create(
                data=base64.b64encode(sample_binary_data).decode()
            ),
        )
        text_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            script=VersionedTextFile.objects.create(
                data=factory.make_string()
            ),
        )
        response = make_node_client().get(
            reverse("commissioning-scripts", args=["latest"])
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "Unexpected response %d: %s"
            % (response.status_code, response.content),
        )
        self.assertIn(
            response["Content-Type"],
            {
                "application/tar",
                "application/x-gtar",
                "application/x-tar",
                "application/x-tgz",
            },
        )
        archive = tarfile.open(fileobj=BytesIO(response.content))
        end_time = ceil(time.time())

        # Validate all builtin scripts are included
        for script_name in NODE_INFO_SCRIPTS.keys():
            path = os.path.join("commissioning.d", script_name)
            member = archive.getmember(path)
            self.assertGreaterEqual(member.mtime, start_time)
            self.assertLessEqual(member.mtime, end_time)
            self.assertEqual(0o755, member.mode)

        # Validate custom binary commissioning script
        path = os.path.join("commissioning.d", binary_script.name)
        member = archive.getmember(path)
        self.assertGreaterEqual(member.mtime, start_time)
        self.assertLessEqual(member.mtime, end_time)
        self.assertEqual(0o755, member.mode)
        self.assertEqual(sample_binary_data, archive.extractfile(path).read())

        # Validate custom text commissioning script
        path = os.path.join("commissioning.d", text_script.name)
        member = archive.getmember(path)
        self.assertGreaterEqual(member.mtime, start_time)
        self.assertLessEqual(member.mtime, end_time)
        self.assertEqual(0o755, member.mode)
        self.assertEqual(
            text_script.script.data,
            archive.extractfile(path).read().decode("utf-8"),
        )

    def test_other_user_than_node_cannot_signal_commissioning_result(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        client = MAASSensibleOAuthClient(factory.make_User())
        response = call_signal(client)
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def test_signaling_commissioning_result_does_not_affect_other_node(self):
        other_node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.COMMISSIONING, reload_object(other_node).status
        )

    def test_signaling_commissioning_OK_repopulates_tags_and_status_msg(self):
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node"
        )
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node)
        response = call_signal(
            client, status=SIGNAL_STATUS.OK, script_result=0
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)
        populate_tags_for_single_node.assert_called_once_with(ANY, node)

    def test_signaling_commissioning_OK_moves_node_to_new_when_enlisting(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        nmd = NodeMetadata.objects.create(
            node=node, key="enlisting", value="True"
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(NODE_STATUS.NEW, reload_object(node).status)
        self.assertIsNone(reload_object(nmd))

    def test_signaling_commissioning_OK_repopulates_tags_when_enlisting(self):
        # Regression test for LP:1787492
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node"
        )
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        nmd = NodeMetadata.objects.create(
            node=node, key="enlisting", value="True"
        )
        client = make_node_client(node)
        response = call_signal(
            client, status=SIGNAL_STATUS.OK, script_result=0
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.NEW, reload_object(node).status)
        self.assertIsNone(reload_object(nmd))
        populate_tags_for_single_node.assert_called_once_with(ANY, node)

    def test_signaling_commissioning_other_keeps_enlisting_tag(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        nmd = NodeMetadata.objects.create(
            node=node, key="enlisting", value="True"
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=factory.pick_choice(
                SIGNAL_STATUS_CHOICES,
                but_not=[SIGNAL_STATUS.OK, SIGNAL_STATUS.FAILED],
            ),
        )
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(nmd, reload_object(nmd))

    def test_signaling_commissioning_when_pod_in_any_state(self):
        pod = factory.make_Pod()
        node = factory.make_Node(with_empty_script_sets=True)
        pod.hints.nodes.add(node)
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.WORKING)
        self.assertEqual(response.status_code, http.client.OK)

    def test_signaling_commissioning_when_deployed_overwrites(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, with_empty_script_sets=True
        )
        script_result = factory.make_ScriptResult(
            node.current_commissioning_script_set, status=SCRIPT_STATUS.PASSED
        )
        client = make_node_client(node=node)
        new_result = factory.make_string().encode()
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result=0,
            files={
                script_result.name: new_result,
                f"{script_result.name}.out": new_result,
                f"{script_result.name}.err": b"",
                f"{script_result.name}.yaml": b"",
            },
        )
        script_result = reload_object(script_result)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(new_result, script_result.output)
        self.assertEqual(new_result, script_result.stdout)
        self.assertEqual(b"", script_result.stderr)
        self.assertEqual(b"", script_result.result)

    def test_signaling_requires_status_code(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        url = reverse("metadata-version", args=["latest"])
        response = client.post(url, {"op": "signal"})
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_signaling_rejects_unknown_status_code(self):
        response = call_signal(status=factory.make_string())
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_signaling_refuses_if_machine_in_unexpected_state(self):
        machine = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        client = make_node_client(node=machine)
        response = call_signal(client)
        self.assertEqual(response.status_code, http.client.CONFLICT)
        self.assertEqual(
            response.content.decode(settings.DEFAULT_CHARSET),
            "Machine status isn't valid (status is Allocated)",
        )

    def test_signaling_accepts_non_machine_results(self):
        node = factory.make_Node(
            with_empty_script_sets=True,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]
            ),
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        client = make_node_client(node=node)
        exit_status = random.randint(0, 255)
        output = factory.make_string()
        response = call_signal(
            client,
            script_result=exit_status,
            files={script_result.name: output.encode("ascii")},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        script_result = reload_object(script_result)
        self.assertEqual(exit_status, script_result.exit_status)
        self.assertEqual(output, script_result.output.decode("utf-8"))

    def test_signaling_accepts_WORKING_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.WORKING)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def test_signaling_stores_exit_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        client = make_node_client(node=node)
        exit_status = random.randint(0, 255)
        response = call_signal(
            client,
            script_result=exit_status,
            files={script_result.name: factory.make_string().encode("ascii")},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        script_result = reload_object(script_result)
        self.assertEqual(exit_status, script_result.exit_status)

    def test_signaling_stores_empty_script_result(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        client = make_node_client(node=node)
        response = call_signal(
            client,
            script_result=random.randint(0, 255),
            files={script_result.name: b""},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        script_result = reload_object(script_result)
        self.assertEqual(b"", script_result.stdout)

    def test_signaling_WORKING_keeps_owner(self):
        user = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        node.owner = user
        node.save()
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.WORKING)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(user, reload_object(node).owner)

    def test_signaling_commissioning_success_node_ready_and_status_msg(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        event = Event.objects.get(node=node)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)
        self.assertEqual(event.type.name, EVENT_TYPES.READY)

    def test_signaling_commissioning_success_is_idempotent(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        call_signal(client, status=SIGNAL_STATUS.OK)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_signaling_commissioning_failure_deletes_enlisting(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        nmd = NodeMetadata.objects.create(
            node=node, key="enlisting", value="True"
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.FAILED)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status
        )
        self.assertIsNone(reload_object(nmd))

    def test_signaling_commissioning_failure_makes_node_failed_tests(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.FAILED)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status
        )
        for script_result in node.current_testing_script_set:
            self.assertEqual(SCRIPT_STATUS.ABORTED, script_result.status)

    def test_signaling_commissioning_failure_does_not_populate_tags(self):
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node"
        )
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.FAILED)
        self.assertEqual(http.client.OK, response.status_code)
        populate_tags_for_single_node.assert_not_called()

    def test_signaling_commissioning_clears_status_expires(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            status_expires=datetime.now(timezone.utc),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.WORKING)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertIsNone(reload_object(node).status_expires)

    def test_signaling_commissioning_failure_is_idempotent(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        call_signal(client, status=SIGNAL_STATUS.FAILED)
        response = call_signal(client, status=SIGNAL_STATUS.FAILED)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status
        )

    def test_signaling_commissioning_failure_sets_node_error(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        error_text = factory.make_string()
        response = call_signal(
            client, status=SIGNAL_STATUS.FAILED, error=error_text
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(error_text, reload_object(node).error)

    def test_signaling_no_error_clears_existing_error(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            error=factory.make_string(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual("", reload_object(node).error)

    def test_signaling_stores_files_for_any_status(self):
        self.useFixture(SignalsDisabled("power"))
        statuses = ["WORKING", "OK", "FAILED"]
        nodes = {}
        script_results = {}
        for status in statuses:
            node = factory.make_Node(
                status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
            )
            script_result = (
                node.current_commissioning_script_set.scriptresult_set.first()
            )
            script_result.status = SCRIPT_STATUS.RUNNING
            script_result.save()
            nodes[status] = node
            script_results[status] = script_result
        for status, node in nodes.items():
            script_result = script_results[status]
            client = make_node_client(node=node)
            exit_status = random.randint(0, 10)
            call_signal(
                client,
                status=status,
                script_result=exit_status,
                files={script_result.name: factory.make_bytes()},
            )
        for script_result in script_results.values():
            self.assertIsNotNone(script_result.stdout)

    def test_signaling_stores_files_releasing(self):
        self.useFixture(SignalsDisabled("power"))
        script = factory.make_Script(script_type=SCRIPT_TYPE.RELEASE)
        script_result = factory.make_ScriptResult(
            script=script, status=SCRIPT_STATUS.RUNNING
        )
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        node.current_release_script_set = script_result.script_set
        node.save()
        client = make_node_client(node=node)
        call_signal(
            client,
            status="OK",
            script_result=0,
            files={script_result.name: factory.make_bytes()},
        )
        self.assertIsNotNone(script_result.stdout)

    def test_signal_stores_file_contents(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        client = make_node_client(node=node)
        text = factory.make_string().encode("ascii")
        exit_status = random.randint(0, 255)
        response = call_signal(
            client, script_result=exit_status, files={script_result.name: text}
        )
        script_result = reload_object(script_result)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(text, script_result.output)

    def test_signal_stores_binary(self):
        unicode_text = "<\u2621>"
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        client = make_node_client(node=node)
        exit_status = random.randint(0, 10)
        response = call_signal(
            client,
            script_result=exit_status,
            files={script_result.name: unicode_text.encode("utf-8")},
        )
        script_result = reload_object(script_result)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(unicode_text.encode("utf-8"), script_result.output)

    def test_signal_stores_multiple_files(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        script_results = []
        contents = {}
        for script_result in node.current_commissioning_script_set:
            script_result.status = SCRIPT_STATUS.RUNNING
            script_result.save()
            script_results.append(script_result)

            contents[script_result.name] = factory.make_string().encode(
                "ascii"
            )

        client = make_node_client(node=node)
        exit_status = random.randint(0, 255)
        response = call_signal(
            client, script_result=exit_status, files=contents
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            contents,
            {
                script_result.name: reload_object(script_result).output
                for script_result in script_results
            },
        )

    def test_signal_stores_files_up_to_documented_size_limit(self):
        # The documented size limit for commissioning result files:
        # one megabyte.  What happens above this limit is none of
        # anybody's business, but files up to this size should work.
        size_limit = 2**20
        contents = factory.make_string(size_limit, spaces=True)
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        client = make_node_client(node=node)
        exit_status = random.randint(0, 255)
        response = call_signal(
            client,
            script_result=exit_status,
            files={script_result.name: contents.encode("utf-8")},
        )
        script_result = reload_object(script_result)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(size_limit, len(script_result.output))

    def test_signal_stores_timeout(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        client = make_node_client(node=node)
        text = factory.make_string().encode("ascii")
        exit_status = random.randint(0, 255)
        response = call_signal(
            client,
            script_result=exit_status,
            files={script_result.name: text},
            status=SIGNAL_STATUS.TIMEDOUT,
        )
        script_result = reload_object(script_result)
        self.assertEqual(http.client.OK, response.status_code)
        script_result = reload_object(script_result)
        self.assertEqual(text, script_result.output)
        self.assertEqual(SCRIPT_STATUS.TIMEDOUT, script_result.status)
        self.assertIsNone(script_result.exit_status)

    def test_signal_current_power_type_mscm_does_not_store_params(self):
        node = factory.make_Node(
            power_type="mscm",
            status=NODE_STATUS.COMMISSIONING,
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        params = dict(
            power_address=factory.make_ipv4_address(),
            power_user=factory.make_string(),
            power_pass=factory.make_string(),
        )
        with SignalsDisabled("power"):
            response = call_signal(
                client,
                power_type="moonshot",
                power_parameters=json.dumps(params),
            )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        node = reload_object(node)
        self.assertEqual("mscm", node.power_type)
        self.assertNotEqual(params, node.get_power_parameters())

    def test_signal_refuses_bad_power_type(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        response = call_signal(client, power_type="foo")
        self.assertEqual(response.status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            "Bad power_type 'foo'",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_signal_power_type_stores_params(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        params = dict(
            power_address=factory.make_ipv4_address(),
            power_user=factory.make_string(),
            power_pass=factory.make_string(),
        )
        response = call_signal(
            client, power_type="ipmi", power_parameters=json.dumps(params)
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        node = reload_object(node)
        self.assertEqual("ipmi", node.power_type)
        self.assertEqual(params, node.get_power_parameters())

    def test_signal_power_type_lower_case_works(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        params = dict(
            power_address=factory.make_ipv4_address(),
            power_user=factory.make_string(),
            power_pass=factory.make_string(),
        )
        response = call_signal(
            client, power_type="ipmi", power_parameters=json.dumps(params)
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        node = reload_object(node)
        self.assertEqual(params, node.get_power_parameters())

    def test_signal_invalid_power_parameters(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, with_empty_script_sets=True
        )
        client = make_node_client(node=node)
        response = call_signal(
            client, power_type="ipmi", power_parameters="badjson"
        )
        self.assertEqual(response.status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            response.content.decode(settings.DEFAULT_CHARSET),
            "Failed to parse JSON power_parameters",
        )

    def test_signaling_commissioning_updates_last_ping(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.WORKING)
        self.assertEqual(response.status_code, http.client.OK)

        end_time = ceil(time.time())
        script_set = node.current_commissioning_script_set
        self.assertGreaterEqual(
            ceil(script_set.last_ping.timestamp()), start_time
        )
        self.assertLessEqual(floor(script_set.last_ping.timestamp()), end_time)

    def test_signaling_commissioning_with_netconf_sets_script_to_netconf(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.APPLYING_NETCONF,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.APPLYING_NETCONF, script_result.status)

    def test_signaling_commissioning_with_install_sets_script_to_install(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = random.choice(
            [SCRIPT_STATUS.PENDING, SCRIPT_STATUS.APPLYING_NETCONF]
        )
        script_result.save()
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.INSTALLING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.INSTALLING, script_result.status)

    def test_signaling_commissioning_with_script_id_sets_script_to_run(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.RUNNING, script_result.status)

    def test_signaling_commissioning_with_script_name_sets_script_to_run(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            name=script_result.name,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.RUNNING, script_result.status)

    def test_signaling_commissioning_with_script_id_ignores_not_pending(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_status = factory.pick_choice(
            SCRIPT_STATUS_CHOICES,
            but_not=[
                SCRIPT_STATUS.PENDING,
                SCRIPT_STATUS.APPLYING_NETCONF,
                SCRIPT_STATUS.INSTALLING,
            ],
        )
        script_result.status = script_status
        script_result.save()
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(script_status, script_result.status)


class TestTestingAPI(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(SignalsDisabled("power"))

    def test_other_user_than_node_cannot_signal_testing_result(self):
        node = factory.make_Node(status=NODE_STATUS.TESTING)
        client = MAASSensibleOAuthClient(factory.make_User())
        response = call_signal(client)
        self.assertEqual(response.status_code, http.client.FORBIDDEN)
        self.assertEqual(NODE_STATUS.TESTING, reload_object(node).status)

    def test_signaling_testing_result_does_not_affect_other_node(self):
        other_node = factory.make_Node(
            status=NODE_STATUS.TESTING, with_empty_script_sets=True
        )
        node = factory.make_Node(
            previous_status=NODE_STATUS.DEPLOYED,
            status=NODE_STATUS.TESTING,
            with_empty_script_sets=True,
        )
        client = make_node_client(node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(NODE_STATUS.TESTING, reload_object(other_node).status)

    def test_signaling_testing_success_moves_node_to_previous_status(self):
        node = factory.make_Node(
            previous_status=NODE_STATUS.DEPLOYED,
            status=NODE_STATUS.TESTING,
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)

    def test_signaling_testing_success_moves_node_to_ready_when_commiss(self):
        node = factory.make_Node(
            previous_status=NODE_STATUS.COMMISSIONING,
            status=NODE_STATUS.TESTING,
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        event = Event.objects.last()
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)
        self.assertEqual(event.type.name, EVENT_TYPES.READY)

    def test_signaling_testing_success_moves_node_to_new_when_enlisting(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING, with_empty_script_sets=True
        )
        nmd = NodeMetadata.objects.create(
            node=node, key="enlisting", value="True"
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(NODE_STATUS.NEW, reload_object(node).status)
        self.assertIsNone(reload_object(nmd))

    def test_signaling_testing_success_moves_node_to_new_when_f_commiss(self):
        node = factory.make_Node(
            previous_status=NODE_STATUS.FAILED_COMMISSIONING,
            status=NODE_STATUS.TESTING,
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        event = Event.objects.last()
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(NODE_STATUS.NEW, reload_object(node).status)
        self.assertEqual(event.type.name, EVENT_TYPES.NEW)

    def test_signaling_testing_success_does_not_clear_owner(self):
        node = factory.make_Node(
            previous_status=NODE_STATUS.DEPLOYED,
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(node.owner, reload_object(node).owner)

    def test_signaling_testing_failure_makes_node_failed(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.FAILED)
        event = Event.objects.last()
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(
            NODE_STATUS.FAILED_TESTING, reload_object(node).status
        )
        self.assertEqual(event.type.name, EVENT_TYPES.FAILED_TESTING)
        self.assertEqual(
            SCRIPT_STATUS.ABORTED, node.current_commissioning_script_set.status
        )
        self.assertEqual(
            SCRIPT_STATUS.ABORTED, node.current_testing_script_set.status
        )

    def test_signaling_testing_testing_transitions_to_testing(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.TESTING)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(NODE_STATUS.TESTING, reload_object(node).status)

    def test_signaling_testing_updates_last_ping(self):
        start_time = floor(time.time())
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.WORKING)
        self.assertEqual(response.status_code, http.client.OK)

        end_time = ceil(time.time())
        script_set = node.current_testing_script_set
        self.assertGreaterEqual(
            ceil(script_set.last_ping.timestamp()), start_time
        )
        self.assertLessEqual(floor(script_set.last_ping.timestamp()), end_time)

    def test_signaling_testing_creates_status_message_package_install(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_testing_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.INSTALLING,
            script_result_id=script_result.id,
        )
        event = Event.objects.get(node=node)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(event.type.name, EVENT_TYPES.RUNNING_TEST)

    def test_signaling_testing_creates_status_message_no_package_install(self):
        error = "Starting smartctl-validate (id: 421, script_version_id: 1)"
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_testing_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            error=error,
            script_result_id=script_result.id,
        )
        event = Event.objects.get(node=node)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual(event.type.name, EVENT_TYPES.RUNNING_TEST)

    def test_signaling_testing_with_netconf_sets_script_to_netconf(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_testing_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.APPLYING_NETCONF,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.APPLYING_NETCONF, script_result.status)

    def test_signaling_testing_with_install_sets_script_to_install(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_testing_script_set.scriptresult_set.first()
        )
        script_result.status = random.choice(
            [SCRIPT_STATUS.PENDING, SCRIPT_STATUS.APPLYING_NETCONF]
        )
        script_result.save()
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.INSTALLING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.INSTALLING, script_result.status)

    def test_signaling_testing_with_script_id_sets_script_to_run(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_testing_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.RUNNING, script_result.status)

    def test_signaling_testing_with_script_name_sets_script_to_run(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_testing_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            name=script_result.name,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(SCRIPT_STATUS.RUNNING, script_result.status)

    def test_signaling_testing_with_script_id_ignores_not_pending(self):
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_testing_script_set.scriptresult_set.first()
        )
        script_status = factory.pick_choice(
            SCRIPT_STATUS_CHOICES,
            but_not=[
                SCRIPT_STATUS.PENDING,
                SCRIPT_STATUS.APPLYING_NETCONF,
                SCRIPT_STATUS.INSTALLING,
            ],
        )
        script_result.status = script_status
        script_result.save()
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        script_result = reload_object(script_result)
        self.assertEqual(script_status, script_result.status)

    def test_signaling_testing_resets_status_expires(self):
        factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        node = factory.make_Node(
            status=NODE_STATUS.TESTING,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        node.status_expires = datetime.now(timezone.utc)
        node.save()
        script_result = (
            node.current_testing_script_set.scriptresult_set.first()
        )
        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result_id=script_result.id,
        )
        self.assertEqual(response.status_code, http.client.OK)

        node = reload_object(node)
        self.assertIsNone(node.status_expires)


class TestNewAPI(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(SignalsDisabled("power"))

    def test_signal_commissioning(self):
        load_builtin_scripts()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        # When creating a new ScriptSet for commissioning during enlistment
        # only the builtin commissioning scripts should be added.
        factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
        factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, tags=["commissioning"]
        )

        client = make_node_client(node)
        response = call_signal(client, status=SIGNAL_STATUS.COMMISSIONING)

        self.assertEqual(response.status_code, http.client.OK)

        node = reload_object(node)
        self.assertIsNotNone(node.current_commissioning_script_set)
        self.assertEqual(
            NODE_INFO_SCRIPTS.keys(),
            {script.name for script in node.current_commissioning_script_set},
        )
        self.assertIsNone(node.current_testing_script_set)
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)

    def test_signal_commissioning_only_creates_scriptsets_when_needed(self):
        load_builtin_scripts()
        # This happens when commissioning is started by the user with correct
        # power parameters but an invalid or missing boot MAC.
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, tags=["commissioning"]
        )
        commissioning = ScriptSet.objects.create_commissioning_script_set(node)
        testing = ScriptSet.objects.create_testing_script_set(node)
        node.current_commissioning_script_set = commissioning
        node.current_testing_script_set = testing
        node.save()

        client = make_node_client(node)
        response = call_signal(client, status=SIGNAL_STATUS.COMMISSIONING)

        self.assertEqual(response.status_code, http.client.OK)

        node = reload_object(node)
        self.assertEqual(commissioning, node.current_commissioning_script_set)
        self.assertEqual(testing, node.current_testing_script_set)

    def test_other_user_than_node_cannot_signal_commissioning(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)

        client = MAASSensibleOAuthClient(factory.make_User())
        response = call_signal(client)

        self.assertEqual(response.status_code, http.client.FORBIDDEN)
        self.assertEqual(NODE_STATUS.NEW, reload_object(node).status)

    def test_signaling_commissioning_result_does_not_affect_other_node(self):
        other_node = factory.make_Node(status=NODE_STATUS.NEW)
        node = factory.make_Node(status=NODE_STATUS.NEW)

        client = make_node_client(node)
        response = call_signal(client, status=SIGNAL_STATUS.COMMISSIONING)

        self.assertEqual(response.status_code, http.client.OK)

        other_node = reload_object(other_node)
        self.assertIsNone(other_node.current_commissioning_script_set)
        self.assertIsNone(other_node.current_testing_script_set)
        self.assertEqual(NODE_STATUS.NEW, other_node.status)
        self.assertIsNone(other_node.min_hwe_kernel)

    def test_signaling_other_is_ignored(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)

        client = make_node_client(node)
        response = call_signal(
            client,
            status=factory.pick_choice(
                SIGNAL_STATUS_CHOICES, but_not=[SIGNAL_STATUS.COMMISSIONING]
            ),
        )

        self.assertEqual(response.status_code, http.client.OK)

        node = reload_object(node)
        self.assertIsNone(node.current_commissioning_script_set)
        self.assertIsNone(node.current_testing_script_set)
        self.assertEqual(NODE_STATUS.NEW, node.status)
        self.assertIsNone(node.min_hwe_kernel)


class TestDiskErasingAPI(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(SignalsDisabled("power"))

    def test_signaling_erasing_failure_makes_node_failed_erasing(self):
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=factory.make_User()
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.FAILED)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DISK_ERASING, reload_object(node).status
        )

    def test_signaling_erasing_ok_releases_node(self):
        self.patch(Node, "_stop")
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING,
            owner=factory.make_User(),
            power_state=POWER_STATE.ON,
            power_type="virsh",
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(node).status)


class TestRescueModeAPI(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(SignalsDisabled("power"))

    def test_signaling_rescue_mode_failure_makes_failed_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.ENTERING_RESCUE_MODE,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.FAILED)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_ENTERING_RESCUE_MODE, reload_object(node).status
        )

    def test_signaling_entering_rescue_mode_ok_changes_status_and_msg(self):
        node = factory.make_Node(
            status=NODE_STATUS.ENTERING_RESCUE_MODE,
            owner=factory.make_User(),
            power_state=POWER_STATE.ON,
            power_type="virsh",
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        event = Event.objects.get(node=node)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.RESCUE_MODE, reload_object(node).status)
        self.assertEqual(event.type.name, EVENT_TYPES.RESCUE_MODE)

    def test_signaling_entering_rescue_mode_does_not_set_owner_to_None(self):
        node = factory.make_Node(
            status=NODE_STATUS.ENTERING_RESCUE_MODE,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        client = make_node_client(node=node)
        response = call_signal(client, status=SIGNAL_STATUS.OK)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertIsNotNone(reload_object(node).owner)

    def test_rescue_mode_accepts_commissioning_results(self):
        node = factory.make_Node(
            status=NODE_STATUS.RESCUE_MODE,
            owner=factory.make_User(),
            with_empty_script_sets=True,
        )
        script_result = random.choice(
            list(node.current_commissioning_script_set)
        )
        exit_status = random.randint(0, 255)
        out = factory.make_string().encode()

        client = make_node_client(node=node)
        response = call_signal(
            client,
            status=SIGNAL_STATUS.WORKING,
            script_result=exit_status,
            script_result_id=script_result.id,
            files={script_result.name: out},
        )

        script_result = reload_object(script_result)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(exit_status, script_result.exit_status)
        self.assertEqual(out, script_result.output)
        if exit_status == 0:
            self.assertEqual(SCRIPT_STATUS.PASSED, script_result.status)
        else:
            self.assertEqual(SCRIPT_STATUS.FAILED, script_result.status)


class TestByMACMetadataAPI(MAASServerTestCase):
    def test_api_retrieves_node_metadata_by_mac(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        iface = node.get_boot_interface()
        url = reverse(
            "metadata-meta-data-by-mac",
            args=["latest", iface.mac_address, "instance-id"],
        )
        response = self.client.get(url)
        self.assertEqual(
            (http.client.OK.value, iface.node_config.node.system_id),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_api_retrieves_node_userdata_by_mac(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.COMMISSIONING
        )
        iface = node.get_boot_interface()
        user_data = factory.make_string().encode("ascii")
        NodeUserData.objects.set_user_data(iface.node_config.node, user_data)
        url = reverse(
            "metadata-user-data-by-mac", args=["latest", iface.mac_address]
        )
        response = self.client.get(url)
        self.assertEqual(
            (http.client.OK, user_data),
            (response.status_code, response.content),
        )

    def test_api_normally_disallows_anonymous_node_metadata_access(self):
        self.patch(settings, "ALLOW_UNSAFE_METADATA_ACCESS", False)
        node = factory.make_Node_with_Interface_on_Subnet()
        iface = node.get_boot_interface()
        url = reverse(
            "metadata-meta-data-by-mac",
            args=["latest", iface.mac_address, "instance-id"],
        )
        response = self.client.get(url)
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestNetbootOperationAPI(MAASServerTestCase):
    def test_netboot_off(self):
        node = factory.make_Node(netboot=True, power_type="hmcz")
        mock_power_control_node = self.patch(api.Node, "_power_control_node")
        mock_power_control_node.return_value = succeed(None)
        client = make_node_client(node=node)
        url = reverse("metadata-version", args=["latest"])
        response = client.post(url, {"op": "netboot_off"})
        node = reload_object(node)
        self.assertFalse(node.netboot, response)
        mock_power_control_node.assert_called_with(
            ANY,
            None,
            node.get_effective_power_info(),
            node._get_boot_order(False),
        )

    def test_netboot_on(self):
        node = factory.make_Node(netboot=False, power_type="hmcz")
        mock_power_control_node = self.patch(api.Node, "_power_control_node")
        mock_power_control_node.return_value = succeed(None)
        client = make_node_client(node=node)
        url = reverse("metadata-version", args=["latest"])
        response = client.post(url, {"op": "netboot_on"})
        node = reload_object(node)
        self.assertTrue(node.netboot, response)
        mock_power_control_node.assert_called_with(
            ANY,
            None,
            node.get_effective_power_info(),
            node._get_boot_order(True),
        )


class TestAnonymousAPI(MAASServerTestCase):
    def test_anonymous_netboot_off(self):
        node = factory.make_Node(netboot=True, power_type="hmcz")
        mock_power_control_node = self.patch(api.Node, "_power_control_node")
        mock_power_control_node.return_value = succeed(None)
        anon_netboot_off_url = reverse(
            "metadata-node-by-id", args=["latest", node.system_id]
        )
        response = self.client.post(
            anon_netboot_off_url, {"op": "netboot_off"}
        )
        node = reload_object(node)
        self.assertEqual(
            (http.client.OK, False),
            (response.status_code, node.netboot),
            response,
        )
        mock_power_control_node.assert_called_with(
            ANY,
            None,
            node.get_effective_power_info(),
            node._get_boot_order(False),
        )

    def test_anonymous_get_enlist_preseed(self):
        # The preseed for enlistment can be obtained anonymously.
        anon_enlist_preseed_url = reverse(
            "metadata-enlist-preseed", args=["latest"]
        )
        # Fake the preseed so we're just exercising the view.
        fake_preseed = factory.make_string()
        self.patch(api, "get_enlist_preseed", Mock(return_value=fake_preseed))
        response = self.client.get(
            anon_enlist_preseed_url, {"op": "get_enlist_preseed"}
        )
        self.assertEqual(
            (http.client.OK.value, "text/plain", fake_preseed),
            (
                response.status_code,
                response["Content-Type"],
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
            response,
        )

    def test_anonymous_get_enlist_preseed_uses_rack_url(self):
        url = "http://%s" % factory.make_name("host")
        network = IPNetwork("10.1.1/24")
        ip = factory.pick_ip_in_network(network)
        rack = factory.make_RackController(interface=True, url=url)
        nic = rack.get_boot_interface()
        vlan = nic.vlan
        subnet = factory.make_Subnet(cidr=str(network.cidr), vlan=vlan)
        rack_ip = factory.make_StaticIPAddress(subnet=subnet, interface=nic)
        vlan.dhcp_on = True
        vlan.primary_rack = rack
        vlan.save()
        anon_enlist_preseed_url = reverse(
            "metadata-enlist-preseed", args=["latest"]
        )
        response = self.client.get(
            anon_enlist_preseed_url,
            {"op": "get_enlist_preseed"},
            REMOTE_ADDR=ip,
        )
        # Test client uses hostname 'testserver'. Ensures that the
        # `build_absolute_uri` is used on the test.
        self.assertIn(
            f"http://{rack_ip.ip}:5248/MAAS/",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_anonymous_get_enlist_preseed_uses_detected_region_ip(self):
        request_ip = get_source_address("8.8.8.8")
        expected_source_ip = get_source_address(request_ip)
        rack = factory.make_RackController(url="")
        find_rack_controller_mock = self.patch(api, "find_rack_controller")
        find_rack_controller_mock.return_value = rack
        get_default_region_ip_mock = self.patch(api, "get_default_region_ip")
        get_default_region_ip_mock.return_value = expected_source_ip
        anon_enlist_preseed_url = reverse(
            "metadata-enlist-preseed", args=["latest"]
        )
        response = self.client.get(
            anon_enlist_preseed_url,
            {"op": "get_enlist_preseed"},
            REMOTE_ADDR=request_ip,
        )
        self.assertIn(
            expected_source_ip,
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_anonymous_get_preseed(self):
        # The preseed for a node can be obtained anonymously.
        node = factory.make_Node()
        anon_node_url = reverse(
            "metadata-node-by-id", args=["latest", node.system_id]
        )
        response = self.client.get(anon_node_url, {"op": "get_preseed"})
        self.assertEqual(response.status_code, http.client.OK)


class TestEnlistViews(MAASServerTestCase):
    """Tests for the enlistment metadata views."""

    def test_get_instance_id(self):
        # instance-id must be available
        md_url = reverse(
            "enlist-metadata-meta-data", args=["latest", "instance-id"]
        )
        response = self.client.get(md_url)
        self.assertEqual(
            (http.client.OK.value, "text/plain"),
            (response.status_code, response["Content-Type"]),
        )
        # just insist content is non-empty. It doesn't matter what it is.
        self.assertTrue(response.content)

    def test_get_hostname(self):
        # instance-id must be available
        md_url = reverse(
            "enlist-metadata-meta-data", args=["latest", "local-hostname"]
        )
        response = self.client.get(md_url)
        self.assertEqual(
            (http.client.OK, "text/plain"),
            (response.status_code, response["Content-Type"]),
        )
        # just insist content is non-empty. It doesn't matter what it is.
        self.assertTrue(response.content)

    def test_public_keys_returns_empty(self):
        # An enlisting node has no SSH keys, but it does request them.
        # If the node insists, we give it the empty list.
        md_url = reverse(
            "enlist-metadata-meta-data", args=["latest", "public-keys"]
        )
        response = self.client.get(md_url)
        self.assertEqual(
            (http.client.OK, ""),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_metadata_bogus_is_404(self):
        md_url = reverse("enlist-metadata-meta-data", args=["latest", "BOGUS"])
        response = self.client.get(md_url)
        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_get_userdata(self):
        # instance-id must be available
        ud_url = reverse("enlist-metadata-user-data", args=["latest"])
        response = self.client.get(ud_url)
        self.assertEqual(response.status_code, http.client.OK)

        self.assertEqual("text/plain", response["Content-Type"])
        self.assertNotEqual(
            "", response.content.decode(settings.DEFAULT_CHARSET)
        )

    def test_metadata_list(self):
        # /enlist/latest/metadata request should list available keys
        md_url = reverse("enlist-metadata-meta-data", args=["latest", ""])
        response = self.client.get(md_url)
        self.assertEqual(
            (http.client.OK, "text/plain"),
            (response.status_code, response["Content-Type"]),
        )
        content = response.content.decode(
            settings.DEFAULT_CHARSET
        ).splitlines()
        for needle in ("instance-id", "local-hostname"):
            self.assertIn(needle, content)

    def test_api_version_contents_list(self):
        # top level api (/enlist/latest/) must list 'metadata' and 'userdata'
        md_url = reverse("enlist-version", args=["latest"])
        response = self.client.get(md_url)
        self.assertEqual(
            (http.client.OK, "text/plain"),
            (response.status_code, response["Content-Type"]),
        )
        content = response.content.decode(
            settings.DEFAULT_CHARSET
        ).splitlines()
        for needle in ("user-data", "meta-data"):
            self.assertIn(needle, content)


class TestStoreNodeParameters(APITestCase.ForUser):
    """Tests for `store_node_power_parameters`."""

    def setUp(self):
        super().setUp()
        self.node = factory.make_Node()
        self.save = self.patch(self.node, "save")
        self.request = Mock()

    def test_no_connected_rack_controllers(self):
        # When get_driver_types returns empty dictionary.
        mock_get_driver_types = self.patch(api, "get_driver_types")
        mock_get_driver_types.return_value = {}
        power_type = factory.pick_power_type()
        self.request.POST = {"power_type": power_type}
        with self.assertRaises(ClusterUnavailable) as cm:
            store_node_power_parameters(self.node, self.request)
        self.assertEqual(
            "No rack controllers connected to validate the power_type.",
            str(cm.exception),
        )
        mock_get_driver_types.assert_called_once()

    def test_power_type_not_given(self):
        # When power_type is not specified, nothing happens.
        self.request.POST = {}
        self.node.set_power_config("", {})
        store_node_power_parameters(self.node, self.request)
        self.assertEqual("", self.node.power_type)
        self.assertEqual({}, self.node.get_power_parameters())
        self.save.assert_has_calls([])

    def test_power_type_redfish(self):
        power_parameters = {"foo": [1, 2, 3]}
        self.request.POST = {
            "power_type": "ipmi",
            "power_parameters": json.dumps(power_parameters),
        }
        self.node.set_power_config("redfish", {"node_id": "1"})
        store_node_power_parameters(self.node, self.request)
        self.assertEqual("redfish", self.node.power_type)
        self.assertEqual(
            {**power_parameters, **self.node.get_instance_power_parameters()},
            self.node.get_power_parameters(),
        )
        self.save.assert_has_calls([])

    def test_power_type_redfish_no_parameters(self):
        self.node.set_power_config("redfish", {"node_id": "1"})
        self.request.POST = {}
        store_node_power_parameters(self.node, self.request)
        self.assertEqual("redfish", self.node.power_type)
        self.assertEqual(
            self.node.get_instance_power_parameters(),
            self.node.get_power_parameters(),
        )
        self.save.assert_has_calls([])

    def test_power_type_redfish_update_parameters_from_ipmi(self):
        self.node.set_power_config("redfish", {"foo": 1})
        power_parameters = {"foo": 2, "bar": 3}
        self.request.POST = {
            "power_type": "ipmi",
            "power_parameters": json.dumps(power_parameters),
        }
        store_node_power_parameters(self.node, self.request)
        self.assertEqual("redfish", self.node.power_type)
        self.assertEqual(self.node.get_power_parameters(), power_parameters)
        self.assertEqual(
            self.node.get_instance_power_parameters(),
            self.node.get_power_parameters(),
        )
        self.save.assert_called_once_with()

    def test_power_type_set_but_no_parameters(self):
        # When power_type is valid, it is set. However, if power_parameters is
        # not specified, the node's power_parameters is left alone, and the
        # node is saved.
        self.node.set_power_config("ipmi", {"some": "param"})
        self.request.POST = {"power_type": "virsh"}
        store_node_power_parameters(self.node, self.request)
        self.assertEqual(self.node.power_type, "virsh")
        self.assertEqual({"some": "param"}, self.node.get_power_parameters())
        self.save.assert_called_once_with()

    def test_power_type_set_with_parameters(self):
        # When power_type is valid, and power_parameters is valid JSON, both
        # fields are set on the node, and the node is saved.
        power_type = factory.pick_power_type(but_not=[self.node.power_type])
        power_parameters = {"foo": [1, 2, 3]}
        self.request.POST = {
            "power_type": power_type,
            "power_parameters": json.dumps(power_parameters),
        }
        store_node_power_parameters(self.node, self.request)
        self.assertEqual(power_type, self.node.power_type)
        self.assertEqual(power_parameters, self.node.get_power_parameters())
        self.assertTrue(self.node.bmc.created_by_commissioning)
        self.save.assert_called_once_with()

    def test_power_type_set_with_invalid_parameters(self):
        # When power_type is valid, but power_parameters is invalid JSON, the
        # node is not saved, and an exception is raised.
        power_type = factory.pick_power_type()
        self.request.POST = {
            "power_type": power_type,
            "power_parameters": "Not JSON.",
        }
        self.assertRaises(
            MAASAPIBadRequest,
            store_node_power_parameters,
            self.node,
            self.request,
        )
        self.save.assert_has_calls([])

    def test_invalid_power_type(self):
        # When power_type is invalid, the node is not saved, and an exception
        # is raised.
        self.request.POST = {"power_type": factory.make_name("bogus")}
        self.assertRaises(
            MAASAPIBadRequest,
            store_node_power_parameters,
            self.node,
            self.request,
        )
        self.save.assert_has_calls([])

    def test_unknown_power_type(self):
        # Sometimes a node doesn't know its power type, and will declare its
        # powertype as ''; store_node_power_parameters will store that
        # appropriately.
        power_type = ""
        self.request.POST = {"power_type": ""}
        store_node_power_parameters(self.node, self.request)
        self.assertEqual(power_type, self.node.power_type)
        self.save.assert_called_once_with()
