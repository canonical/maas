# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.base`"""

import random
from unittest.mock import ANY, MagicMock, sentinel

from django.db.models.query import QuerySet
from django.http import HttpRequest
from twisted.internet.defer import succeed

from maasserver.enum import NODE_STATUS, NODE_STATUS_CHOICES_DICT
from maasserver.forms import AdminMachineForm, AdminMachineWithMACAddressesForm
from maasserver.models.node import Device, Node
from maasserver.models.sslkey import SSLKey
from maasserver.models.vlan import VLAN
from maasserver.models.zone import Zone
from maasserver.permissions import NodePermission
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit_hooks, reload_object
from maasserver.websockets import base
from maasserver.websockets.base import (
    Handler,
    HandlerDoesNotExistError,
    HandlerNoSuchMethodError,
    HandlerPermissionError,
    HandlerValidationError,
)
from maastesting import get_testing_timeout
from maastesting.testcase import MAASTestCase
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()


def make_handler(name, **kwargs):
    meta = type("Meta", (object,), kwargs)
    return object.__new__(type(name, (Handler,), {"Meta": meta}))


class TestHandlerMeta(MAASTestCase):
    def test_creates_handler_with_default_meta(self):
        handler = Handler(None, {}, None)
        meta = handler._meta
        self.assertFalse(meta.abstract)
        self.assertEqual(
            meta.allowed_methods,
            [
                "list",
                "get",
                "create",
                "update",
                "delete",
                "set_active",
                "unsubscribe",
            ],
        )

        self.assertEqual(meta.handler_name, "")
        self.assertIsNone(meta.object_class)
        self.assertIsNone(meta.queryset)
        self.assertEqual(meta.pk, "id")
        self.assertIsNone(meta.fields)
        self.assertIsNone(meta.exclude)
        self.assertIsNone(meta.list_fields)
        self.assertIsNone(meta.list_exclude)
        self.assertIsNone(meta.non_changeable)
        self.assertIsNone(meta.form)

    def test_creates_handler_with_options(self):
        handler = make_handler(
            "TestHandler",
            abstract=True,
            allowed_methods=["list"],
            handler_name="testing",
            queryset=Node.objects.all(),
            pk="system_id",
            fields=["hostname", "distro_series"],
            exclude=["system_id"],
            list_fields=["hostname"],
            list_exclude=["hostname"],
            non_changeable=["system_id"],
            form=sentinel.form,
        )
        meta = handler._meta
        self.assertTrue(meta.abstract)
        self.assertEqual(
            meta.allowed_methods,
            ["list"],
        )
        self.assertEqual(meta.handler_name, "testing")
        self.assertIs(meta.object_class, Node)
        self.assertIsInstance(meta.queryset, QuerySet)
        self.assertEqual(meta.pk, "system_id")
        self.assertEqual(meta.fields, ["hostname", "distro_series"])
        self.assertEqual(meta.exclude, ["system_id"])
        self.assertEqual(meta.list_fields, ["hostname"])
        self.assertEqual(meta.list_exclude, ["hostname"])
        self.assertEqual(meta.non_changeable, ["system_id"])
        self.assertIs(meta.form, sentinel.form)

    def test_sets_handler_name_based_on_class_name(self):
        names = [
            ("TestHandler", "test"),
            ("TestHandlerNew", "testnew"),
            ("AlwaysLowerHandler", "alwayslower"),
        ]
        for class_name, handler_name in names:
            obj = make_handler(class_name)
            self.assertEqual(obj._meta.handler_name, handler_name)

    def test_sets_object_class_based_on_queryset(self):
        handler = make_handler("TestHandler", queryset=Node.objects.all())
        self.assertIs(Node, handler._meta.object_class)

    def test_copy_fields_and_excludes_to_list_fields_and_list_excludes(self):
        fields = [factory.make_name("field") for _ in range(3)]
        exclude = [factory.make_name("field") for _ in range(3)]
        handler = make_handler("TestHandler", fields=fields, exclude=exclude)
        self.assertEqual(fields, handler._meta.list_fields)
        self.assertEqual(exclude, handler._meta.list_exclude)

    def test_copy_fields_and_excludes_doesnt_overwrite_lists_if_set(self):
        fields = [factory.make_name("field") for _ in range(3)]
        exclude = [factory.make_name("field") for _ in range(3)]
        list_fields = [factory.make_name("field") for _ in range(3)]
        list_exclude = [factory.make_name("field") for _ in range(3)]
        handler = make_handler(
            "TestHandler",
            fields=fields,
            exclude=exclude,
            list_fields=list_fields,
            list_exclude=list_exclude,
        )
        self.assertEqual(list_fields, handler._meta.list_fields)
        self.assertEqual(list_exclude, handler._meta.list_exclude)


class FakeNodesHandlerMixin:
    def make_nodes_handler(self, **kwargs):
        meta_args = {
            "queryset": Node.objects.all(),
            "object_class": Node,
            "pk": "system_id",
            "pk_type": str,
        }
        meta_args.update(kwargs)
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = make_handler("TestNodesHandler", **meta_args)
        handler.__init__(user, {}, request)
        return handler

    def make_mock_node_with_fields(self, **kwargs):
        return object.__new__(type("MockNode", (object,), kwargs))


class TestHandler(MAASServerTestCase, FakeNodesHandlerMixin):
    def test_full_dehydrate_only_includes_allowed_fields(self):
        handler = self.make_nodes_handler(fields=["hostname", "cpu_count"])
        node = factory.make_Node()
        self.assertEqual(
            {"hostname": node.hostname, "cpu_count": node.cpu_count},
            handler.full_dehydrate(node),
        )

    def test_full_dehydrate_excludes_fields(self):
        handler = self.make_nodes_handler(
            fields=["hostname", "power_type"], exclude=["power_type"]
        )
        node = factory.make_Node()
        self.assertEqual(
            {"hostname": node.hostname}, handler.full_dehydrate(node)
        )

    def test_full_dehydrate_includes_permissions_when_defined(self):
        handler = self.make_nodes_handler(
            fields=["hostname"],
            edit_permission=NodePermission.admin,
            delete_permission=NodePermission.admin,
        )
        handler.user = factory.make_admin()
        node = factory.make_Node()
        self.assertEqual(
            {"hostname": node.hostname, "permissions": ["edit", "delete"]},
            handler.full_dehydrate(node),
        )

    def test_full_dehydrate_only_includes_list_fields_when_for_list(self):
        handler = self.make_nodes_handler(
            list_fields=["cpu_count", "power_state"]
        )
        node = factory.make_Node()
        self.assertEqual(
            {"cpu_count": node.cpu_count, "power_state": node.power_state},
            handler.full_dehydrate(node, for_list=True),
        )

    def test_full_dehydrate_excludes_list_fields_when_for_list(self):
        handler = self.make_nodes_handler(
            list_fields=["cpu_count", "power_state"],
            list_exclude=["cpu_count"],
        )
        node = factory.make_Node()
        self.assertEqual(
            {"power_state": node.power_state},
            handler.full_dehydrate(node, for_list=True),
        )

    def test_full_dehydrate_calls_field_dehydrate_method_if_exists(self):
        handler = self.make_nodes_handler(fields=["hostname"])
        mock_dehydrate_hostname = self.patch(handler, "dehydrate_hostname")
        mock_dehydrate_hostname.return_value = sentinel.hostname
        node = factory.make_Node()
        self.assertEqual(
            {"hostname": sentinel.hostname}, handler.full_dehydrate(node)
        )
        mock_dehydrate_hostname.assert_called_once_with(node.hostname)

    def test_full_dehydrate_calls_final_dehydrate_method(self):
        handler = self.make_nodes_handler(fields=["hostname"])
        mock_dehydrate = self.patch_autospec(handler, "dehydrate")
        mock_dehydrate.return_value = sentinel.final_dehydrate
        node = factory.make_Node()
        self.assertEqual(
            sentinel.final_dehydrate, handler.full_dehydrate(node)
        )
        mock_dehydrate.assert_called_once_with(
            node, {"hostname": node.hostname}, for_list=False
        )

    def test_dehydrate_does_nothing(self):
        handler = self.make_nodes_handler()
        self.assertEqual(
            sentinel.nothing, handler.dehydrate(sentinel.obj, sentinel.nothing)
        )

    def test_full_hydrate_only_doesnt_set_primary_key_field(self):
        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(fields=["system_id", "hostname"])
        node = self.make_mock_node_with_fields(
            system_id=system_id, hostname=factory.make_name("hostname")
        )
        handler.full_hydrate(
            node,
            {
                "system_id": factory.make_name("system_id"),
                "hostname": hostname,
            },
        )
        self.assertEqual(system_id, node.system_id)
        self.assertEqual(hostname, node.hostname)

    def test_full_hydrate_only_sets_allowed_fields(self):
        hostname = factory.make_name("hostname")
        power_state = "on"
        handler = self.make_nodes_handler(fields=["hostname", "power_state"])
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname"),
            power_state="off",
            power_type="ipmi",
        )
        handler.full_hydrate(
            node,
            {
                "hostname": hostname,
                "power_state": power_state,
                "power_type": "manual",
            },
        )
        self.assertEqual(hostname, node.hostname)
        self.assertEqual(power_state, node.power_state)
        self.assertEqual("ipmi", node.power_type)

    def test_full_hydrate_only_sets_non_excluded_fields(self):
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(
            fields=["hostname", "power_state"], exclude=["power_state"]
        )
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname"),
            power_state="off",
            power_type="ipmi",
        )
        handler.full_hydrate(
            node,
            {
                "hostname": hostname,
                "power_state": "on",
                "power_type": "manual",
            },
        )
        self.assertEqual(hostname, node.hostname)
        self.assertEqual("off", node.power_state)
        self.assertEqual("ipmi", node.power_type)

    def test_full_hydrate_only_doesnt_set_fields_not_allowed_to_change(self):
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(
            fields=["hostname", "power_state"], non_changeable=["power_state"]
        )
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname"),
            power_state="off",
            power_type="ipmi",
        )
        handler.full_hydrate(
            node,
            {
                "hostname": hostname,
                "power_state": "on",
                "power_type": "manual",
            },
        )
        self.assertEqual(hostname, node.hostname)
        self.assertEqual("off", node.power_state)
        self.assertEqual("ipmi", node.power_type)

    def test_full_hydrate_calls_fields_hydrate_method_if_present(self):
        call_hostname = factory.make_name("hostname")
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(fields=["hostname"])
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname")
        )
        mock_hydrate_hostname = self.patch(handler, "hydrate_hostname")
        mock_hydrate_hostname.return_value = hostname
        handler.full_hydrate(node, {"hostname": call_hostname})
        self.assertEqual(hostname, node.hostname)
        mock_hydrate_hostname.assert_called_once_with(call_hostname)

    def test_full_hydrate_calls_final_hydrate_method(self):
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(fields=["hostname"])
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname")
        )
        mock_hydrate = self.patch_autospec(handler, "hydrate")
        mock_hydrate.return_value = sentinel.final_hydrate
        self.assertEqual(
            sentinel.final_hydrate,
            handler.full_hydrate(node, {"hostname": hostname}),
        )
        mock_hydrate.assert_called_once_with(node, {"hostname": hostname})

    def test_hydrate_does_nothing(self):
        handler = self.make_nodes_handler()
        self.assertEqual(
            sentinel.obj, handler.hydrate(sentinel.obj, sentinel.nothing)
        )

    def test_get_object_raises_HandlerValidationError(self):
        handler = self.make_nodes_handler()
        self.assertRaises(
            HandlerValidationError, handler.get_object, {"host": "test"}
        )

    def test_get_object_raises_HandlerDoesNotExistError(self):
        handler = self.make_nodes_handler()
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get_object,
            {"system_id": factory.make_name("system_id")},
        )

    def test_get_object_returns_object(self):
        handler = self.make_nodes_handler()
        node = factory.make_Node()
        self.assertEqual(
            node.hostname,
            handler.get_object({"system_id": node.system_id}).hostname,
        )

    def test_get_object_respects_queryset(self):
        handler = self.make_nodes_handler(queryset=Device.objects.all())
        machine = factory.make_Machine()
        device = factory.make_Device()
        returned_device = handler.get_object({"system_id": device.system_id})
        self.assertEqual(device.hostname, returned_device.hostname)
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get_object,
            {"system_id": machine.system_id},
        )

    def test_get_own_object_returns_object(self):
        handler = self.make_nodes_handler(
            queryset=SSLKey.objects.all(), pk="pk"
        )
        owned_sslkey = factory.make_SSLKey(handler.user)
        self.assertEqual(
            owned_sslkey.pk,
            handler.get_own_object({"pk": owned_sslkey.pk}).pk,
        )

    def test_get_own_object_doesnt_return_not_owned_objects(self):
        handler = self.make_nodes_handler(
            queryset=SSLKey.objects.all(), pk="id"
        )
        not_owned_sslkey = factory.make_SSLKey(factory.make_User())
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get_own_object,
            {"id": not_owned_sslkey.id},
        )

    def test_get_queryset(self):
        queryset = MagicMock()
        list_queryset = MagicMock()
        handler = make_handler(
            "TestHandler", queryset=queryset, list_queryset=list_queryset
        )
        self.assertEqual(queryset, handler.get_queryset())

    def test_get_queryset_list(self):
        queryset = MagicMock()
        list_queryset = MagicMock()
        handler = make_handler(
            "TestHandler", queryset=queryset, list_queryset=list_queryset
        )
        self.assertEqual(list_queryset, handler.get_queryset(for_list=True))

    def test_get_queryset_list_only_if_avail(self):
        queryset = MagicMock()
        handler = make_handler("TestHandler", queryset=queryset)
        self.assertEqual(queryset, handler.get_queryset(for_list=True))

    def test_execute_only_allows_meta_allowed_methods(self):
        handler = self.make_nodes_handler(allowed_methods=["list"])
        d = handler.execute("get", {})
        self.assertRaises(HandlerNoSuchMethodError, d.wait, TIMEOUT)

    def test_execute_raises_HandlerNoSuchMethodError(self):
        handler = self.make_nodes_handler(allowed_methods=["extra_method"])
        d = handler.execute("extra_method", {})
        self.assertRaises(HandlerNoSuchMethodError, d.wait, TIMEOUT)

    def test_execute_calls_in_database_thread_with_params(self):
        # Methods are assumed by default to be synchronous and are called in a
        # thread that originates from a specific threadpool.
        handler = self.make_nodes_handler()
        params = {"system_id": factory.make_name("system_id")}
        self.patch(base, "deferToDatabase").return_value = sentinel.thing
        result = handler.execute("get", params).wait(TIMEOUT)
        self.assertIs(result, sentinel.thing)
        base.deferToDatabase.assert_called_once_with(ANY, params)

    def test_execute_track_latency(self):
        mock_metrics = self.patch(PROMETHEUS_METRICS, "update")

        handler = self.make_nodes_handler()
        params = {"system_id": factory.make_name("system_id")}
        self.patch(base, "deferToDatabase").return_value = sentinel.thing
        result = handler.execute("get", params).wait(TIMEOUT)
        self.assertIs(result, sentinel.thing)
        mock_metrics.assert_called_with(
            "maas_websocket_call_latency",
            "observe",
            labels={"call": "testnodes.get"},
            value=ANY,
        )

    def test_list(self):
        output = [{"hostname": factory.make_Node().hostname} for _ in range(3)]
        handler = self.make_nodes_handler(fields=["hostname"])
        self.assertCountEqual(output, handler.list({}))

    def test_list_start(self):
        nodes = [factory.make_Node() for _ in range(6)]
        output = [{"hostname": node.hostname} for node in nodes[3:]]
        handler = self.make_nodes_handler(fields=["hostname"])
        self.assertCountEqual(output, handler.list({"start": nodes[2].id}))

    def test_list_limit(self):
        nodes = [factory.make_Node() for _ in range(6)]
        output = [{"hostname": node.hostname} for node in nodes[:3]]
        handler = self.make_nodes_handler(fields=["hostname"])
        self.assertCountEqual(output, handler.list({"limit": 3}))

    def test_list_start_and_limit(self):
        nodes = [factory.make_Node() for _ in range(9)]
        output = [{"hostname": node.hostname} for node in nodes[3:6]]
        handler = self.make_nodes_handler(fields=["hostname"])
        self.assertCountEqual(
            output, handler.list({"start": nodes[2].id, "limit": 3})
        )

    def test_list_pager_get_one(self):
        nodes = [factory.make_Node() for _ in range(5)]
        handler = self.make_nodes_handler(
            list_fields=["system_id"],
            use_paginated_list=True,
        )
        output = {
            "count": 5,
            "cur_page": 1,
            "num_pages": 2,
            "groups": [
                {
                    "collapsed": False,
                    "count": 5,
                    "name": None,
                    "value": None,
                    "items": [{"system_id": n.system_id} for n in nodes[:3]],
                }
            ],
        }
        self.assertEqual(
            output,
            handler.list(
                {
                    "page_size": 3,
                    "page_number": 1,
                }
            ),
        )

    def test_list_pager_get_second(self):
        nodes = [factory.make_Node() for _ in range(5)]
        handler = self.make_nodes_handler(
            list_fields=["system_id"],
            use_paginated_list=True,
        )
        output = {
            "count": 5,
            "cur_page": 2,
            "num_pages": 2,
            "groups": [
                {
                    "collapsed": False,
                    "count": 5,
                    "name": None,
                    "value": None,
                    "items": [{"system_id": n.system_id} for n in nodes[3:]],
                }
            ],
        }
        self.assertEqual(
            output,
            handler.list(
                {
                    "page_size": 3,
                    "page_number": 2,
                }
            ),
        )

    def test_list_pager_get_invalid(self):
        nodes = [factory.make_Node() for _ in range(5)]
        handler = self.make_nodes_handler(
            list_fields=["system_id"],
            use_paginated_list=True,
        )
        output = {
            "count": 5,
            "cur_page": 1,
            "num_pages": 2,
            "groups": [
                {
                    "collapsed": False,
                    "count": 5,
                    "name": None,
                    "value": None,
                    "items": [{"system_id": n.system_id} for n in nodes[:3]],
                }
            ],
        }
        self.assertEqual(
            output,
            handler.list(
                {
                    "page_size": 3,
                    "page_number": None,
                }
            ),
        )

    def test_list_pager_get_beyond_last(self):
        nodes = [factory.make_Node() for _ in range(5)]
        handler = self.make_nodes_handler(
            list_fields=["system_id"],
            use_paginated_list=True,
        )
        output = {
            "count": 5,
            "cur_page": 2,
            "num_pages": 2,
            "groups": [
                {
                    "collapsed": False,
                    "count": 5,
                    "name": None,
                    "value": None,
                    "items": [{"system_id": n.system_id} for n in nodes[3:]],
                }
            ],
        }
        self.assertEqual(
            output,
            handler.list(
                {
                    "page_size": 3,
                    "page_number": 20,
                }
            ),
        )

    def test_list_adds_to_loaded_pks(self):
        pks = [factory.make_Node().system_id for _ in range(3)]
        handler = self.make_nodes_handler(fields=["hostname"])
        handler.list({})
        self.assertCountEqual(pks, handler.cache["loaded_pks"])

    def test_list_unions_the_loaded_pks(self):
        nodes = [factory.make_Node() for _ in range(3)]
        pks = {node.system_id for node in nodes}
        handler = self.make_nodes_handler(fields=["hostname"])
        # Make two calls to list making sure the loaded_pks contains all of
        # the primary keys listed.
        handler.list({"limit": 1})
        # Nodes are little special: they are referred to by system_id, but
        # ordered by id. This is because system_id is no longer guaranteed to
        # sort from oldest node to newest.
        handler.list({"start": nodes[0].id})
        self.assertCountEqual(pks, handler.cache["loaded_pks"])

    def test_get(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler(fields=["hostname"])
        self.assertEqual(
            {"hostname": node.hostname},
            handler.get({"system_id": node.system_id}),
        )

    def test_get_raises_permission_error(self):
        node = factory.make_Node()
        # Set the permission to admin to force the error.
        handler = self.make_nodes_handler(
            fields=["hostname"], view_permission=NodePermission.admin
        )
        self.assertRaises(
            HandlerPermissionError, handler.get, {"system_id": node.system_id}
        )

    def test_create_without_form(self):
        # Use a zone as its simple and easy to create without a form, unlike
        # Node which requires a form.
        handler = make_handler(
            "TestZoneHandler",
            queryset=Zone.objects.all(),
            fields=["name", "description"],
        )
        name = factory.make_name("zone")
        json_obj = handler.create({"name": name})
        self.assertEqual({"name": name, "description": ""}, json_obj)
        self.assertEqual(name, Zone.objects.get(name=name).name)

    def test_create_without_form_uses_object_id(self):
        # Uses a VLAN, which only requires a Fabric.
        handler = make_handler(
            "TestVLANHandler",
            queryset=VLAN.objects.all(),
            fields=["fabric", "vid"],
        )
        fabric = factory.make_Fabric()
        vid = random.randint(1, 4094)
        json_obj = handler.create({"vid": vid, "fabric": fabric.id})
        self.assertEqual({"vid": vid, "fabric": fabric.id}, json_obj)
        vlan = VLAN.objects.get(vid=vid)
        self.assertEqual(vid, vlan.vid)
        self.assertEqual(fabric, fabric)

    def test_create_with_form_creates_node(self):
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        handler = self.make_nodes_handler(
            fields=["hostname", "architecture"],
            form=AdminMachineWithMACAddressesForm,
        )
        handler.user = factory.make_admin()

        with post_commit_hooks:
            json_obj = handler.create(
                {
                    "hostname": hostname,
                    "architecture": arch,
                    "mac_addresses": [factory.make_mac_address()],
                }
            )

        self.assertEqual(
            {"hostname": hostname, "architecture": arch}, json_obj
        )

    def test_create_with_form_uses_form_from_get_form_class(self):
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        handler = self.make_nodes_handler(fields=["hostname", "architecture"])
        handler.user = factory.make_admin()
        self.patch(
            handler, "get_form_class"
        ).return_value = AdminMachineWithMACAddressesForm

        with post_commit_hooks:
            json_obj = handler.create(
                {
                    "hostname": hostname,
                    "architecture": arch,
                    "mac_addresses": [factory.make_mac_address()],
                }
            )
        self.assertEqual(
            {"hostname": hostname, "architecture": arch}, json_obj
        )

    def test_create_raised_permission_error(self):
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        handler = self.make_nodes_handler(fields=["hostname", "architecture"])
        self.patch(
            handler, "get_form_class"
        ).return_value = AdminMachineWithMACAddressesForm
        self.assertRaises(
            HandlerPermissionError,
            handler.create,
            {
                "hostname": hostname,
                "architecture": arch,
                "mac_addresses": [factory.make_mac_address()],
            },
        )

    def test_create_with_form_passes_request_with_user_set(self):
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        mock_form = MagicMock()
        mock_form.return_value.is_valid.return_value = True
        mock_form.return_value.save.return_value = factory.make_Node()
        handler = self.make_nodes_handler(fields=[], form=mock_form)
        handler.create({"hostname": hostname, "architecture": arch})
        # Extract the passed request.
        passed_request = mock_form.call_args_list[0][1]["request"]
        self.assertIs(handler.user, passed_request.user)

    def test_create_with_form_raises_HandlerValidationError(self):
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        handler = self.make_nodes_handler(
            fields=["hostname", "architecture"],
            form=AdminMachineWithMACAddressesForm,
        )
        handler.user = factory.make_admin()
        self.assertRaises(
            HandlerValidationError,
            handler.create,
            {"hostname": hostname, "architecture": arch},
        )

    def test_update_without_form(self):
        handler = self.make_nodes_handler(fields=["hostname"])
        node = factory.make_Node()
        hostname = factory.make_name("hostname")

        with post_commit_hooks:
            json_obj = handler.update(
                {"system_id": node.system_id, "hostname": hostname}
            )

        self.assertEqual({"hostname": hostname}, json_obj)
        self.assertEqual(reload_object(node).hostname, hostname)

    def test_update_with_form_updates_node(self):
        arch = make_usable_architecture(self)
        node = factory.make_Node(architecture=arch, power_type="manual")
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(
            fields=["hostname"], form=AdminMachineForm
        )
        handler.user = factory.make_admin()

        with post_commit_hooks:
            json_obj = handler.update(
                {"system_id": node.system_id, "hostname": hostname}
            )
        self.assertEqual({"hostname": hostname}, json_obj)
        self.assertEqual(reload_object(node).hostname, hostname)

    def test_update_with_form_uses_form_from_get_form_class(self):
        arch = make_usable_architecture(self)
        node = factory.make_Node(architecture=arch, power_type="manual")
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(fields=["hostname"])
        handler.user = factory.make_admin()
        self.patch(handler, "get_form_class").return_value = AdminMachineForm

        with post_commit_hooks:
            json_obj = handler.update(
                {"system_id": node.system_id, "hostname": hostname}
            )

        self.assertEqual({"hostname": hostname}, json_obj)
        self.assertEqual(reload_object(node).hostname, hostname)

    def test_update_with_form_raises_permission_error(self):
        arch = make_usable_architecture(self)
        node = factory.make_Node(architecture=arch, power_type="manual")
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(fields=["hostname"])
        self.patch(handler, "get_form_class").return_value = AdminMachineForm
        self.assertRaises(
            HandlerPermissionError,
            handler.update,
            {"system_id": node.system_id, "hostname": hostname},
        )

    def test_delete_deletes_object(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler()
        handler.delete({"system_id": node.system_id})
        self.assertIsNone(reload_object(node))

    def test_delete_raises_permission_error(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler(
            delete_permission=NodePermission.admin
        )
        self.assertRaises(
            HandlerPermissionError,
            handler.delete,
            {"system_id": node.system_id},
        )

    def test_set_active_does_nothing_if_no_active_obj_and_missing_pk(self):
        handler = self.make_nodes_handler()
        mock_get = self.patch(handler, "get")
        handler.set_active({})
        mock_get.assert_not_called()

    def test_set_active_clears_active_if_missing_pk(self):
        handler = self.make_nodes_handler()
        handler.cache["active_pk"] = factory.make_name("system_id")
        handler.set_active({})
        self.assertNotIn("active_pk", handler.cache)

    def test_set_active_returns_data_and_sets_active(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler(fields=["system_id"])
        node_data = handler.set_active({"system_id": node.system_id})
        self.assertEqual(node_data["system_id"], node.system_id)
        self.assertEqual(handler.cache["active_pk"], node.system_id)

    def test_on_listen_calls_listen(self):
        handler = self.make_nodes_handler()
        pk = factory.make_name("system_id")
        mock_listen = self.patch(handler, "listen")
        mock_listen.side_effect = HandlerDoesNotExistError()
        handler.on_listen(sentinel.channel, sentinel.action, pk)
        mock_listen.assert_called_once_with(
            sentinel.channel, sentinel.action, pk
        )

    def test_on_listen_returns_None_if_unknown_action(self):
        handler = self.make_nodes_handler()
        mock_listen = self.patch(handler, "listen")
        mock_listen.side_effect = HandlerDoesNotExistError()
        self.assertIsNone(
            handler.on_listen(
                sentinel.channel, factory.make_name("action"), sentinel.pk
            )
        )

    def test_on_listen_delete_removes_pk_from_loaded(self):
        handler = self.make_nodes_handler()
        node = factory.make_Node()
        handler.cache["loaded_pks"].add(node.system_id)
        self.assertEqual(
            (handler._meta.handler_name, "delete", node.system_id),
            handler.on_listen(sentinel.channel, "delete", node.system_id),
        )
        self.assertNotIn(
            node.system_id,
            handler.cache["loaded_pks"],
            "on_listen delete did not remove system_id from loaded_pks",
        )

    def test_on_listen_delete_returns_None_if_pk_not_in_loaded(self):
        handler = self.make_nodes_handler()
        node = factory.make_Node()
        self.assertEqual(
            None, handler.on_listen(sentinel.channel, "delete", node.system_id)
        )

    def test_on_listen_create_adds_pk_to_loaded(self):
        handler = self.make_nodes_handler(fields=["hostname"])
        node = factory.make_Node(owner=handler.user)
        self.assertEqual(
            (
                handler._meta.handler_name,
                "create",
                {"hostname": node.hostname},
            ),
            handler.on_listen(sentinel.channel, "create", node.system_id),
        )
        self.assertIn(
            node.system_id,
            handler.cache["loaded_pks"],
            "on_listen create did not add system_id to loaded_pks",
        )

    def test_on_listen_create_returns_update_if_pk_already_known(self):
        handler = self.make_nodes_handler(fields=["hostname"])
        node = factory.make_Node(owner=handler.user)
        handler.cache["loaded_pks"].add(node.system_id)
        self.assertEqual(
            (
                handler._meta.handler_name,
                "update",
                {"hostname": node.hostname},
            ),
            handler.on_listen(sentinel.channel, "create", node.system_id),
        )

    def test_on_listen_update_returns_delete_action_if_obj_is_None(self):
        handler = self.make_nodes_handler()
        node = factory.make_Node()
        handler.cache["loaded_pks"].add(node.system_id)
        self.patch(handler, "listen").return_value = None
        self.assertEqual(
            (handler._meta.handler_name, "delete", node.system_id),
            handler.on_listen(sentinel.channel, "update", node.system_id),
        )
        self.assertNotIn(
            node.system_id,
            handler.cache["loaded_pks"],
            "on_listen update did not remove system_id from loaded_pks",
        )

    def test_on_listen_update_returns_update_action_if_obj_not_None(self):
        handler = self.make_nodes_handler(fields=["hostname"])
        node = factory.make_Node()
        handler.cache["loaded_pks"].add(node.system_id)
        self.assertEqual(
            (
                handler._meta.handler_name,
                "update",
                {"hostname": node.hostname},
            ),
            handler.on_listen(sentinel.channel, "update", node.system_id),
        )
        self.assertIn(
            node.system_id,
            handler.cache["loaded_pks"],
            "on_listen update removed system_id from loaded_pks",
        )

    def test_on_listen_update_returns_create_action_if_not_in_loaded(self):
        handler = self.make_nodes_handler(fields=["hostname"])
        node = factory.make_Node()
        self.assertEqual(
            (
                handler._meta.handler_name,
                "create",
                {"hostname": node.hostname},
            ),
            handler.on_listen(sentinel.channel, "update", node.system_id),
        )
        self.assertIn(
            node.system_id,
            handler.cache["loaded_pks"],
            "on_listen update didnt add system_id to loaded_pks",
        )

    def test_on_listen_update_call_full_dehydrate_for_list_if_not_active(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler()
        handler.cache["loaded_pks"].add(node.system_id)
        mock_dehydrate = self.patch(handler, "full_dehydrate")
        mock_dehydrate.return_value = sentinel.data
        self.assertEqual(
            handler.on_listen(sentinel.channel, "update", node.system_id),
            (handler._meta.handler_name, "update", sentinel.data),
        )
        mock_dehydrate.assert_called_once_with(node, for_list=True)

    def test_on_listen_update_call_full_dehydrate_not_for_list_if_active(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler()
        handler.cache["loaded_pks"].add(node.system_id)
        handler.cache["active_pk"] = node.system_id
        mock_dehydrate = self.patch(handler, "full_dehydrate")
        mock_dehydrate.return_value = sentinel.data
        self.assertEqual(
            handler.on_listen(sentinel.channel, "update", node.system_id),
            (handler._meta.handler_name, "update", sentinel.data),
        )
        mock_dehydrate.assert_called_once_with(node, for_list=False)

    def test_listen_calls_get_object_with_pk_on_other_actions(self):
        handler = self.make_nodes_handler()
        mock_get_object = self.patch(handler, "get_object")
        mock_get_object.return_value = sentinel.obj
        self.assertEqual(
            handler.listen(sentinel.channel, "update", sentinel.pk),
            sentinel.obj,
        )
        mock_get_object.assert_called_once_with(
            {handler._meta.pk: sentinel.pk}
        )

    def test_sort_simple(self):
        for idx in range(3):
            factory.make_Node(hostname=f"host-{idx}")
        handler = self.make_nodes_handler(fields=["hostname"])
        result = handler.list({"sort_key": "hostname"})
        self.assertEqual(3, len(result))
        for idx in range(3):
            self.assertEqual(f"host-{idx}", result[idx]["hostname"])

    def test_sort_reverse(self):
        for idx in range(3):
            factory.make_Node(hostname=f"host-{idx}")
        handler = self.make_nodes_handler(fields=["hostname"])
        result = handler.list(
            {
                "sort_key": "hostname",
                "sort_direction": "descending",
            }
        )
        self.assertEqual(3, len(result))
        for idx in range(3):
            self.assertEqual(f"host-{2 - idx}", result[idx]["hostname"])


class TestHandlerGrouping(MAASServerTestCase, FakeNodesHandlerMixin):
    def make_nodes_handler(self, **kwargs):
        return super().make_nodes_handler(use_paginated_list=True, **kwargs)

    def test_group_simple(self):
        nodes_ready = [
            factory.make_Node(status=NODE_STATUS.READY) for _ in range(3)
        ]
        nodes_new = [
            factory.make_Node(status=NODE_STATUS.NEW) for _ in range(2)
        ]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list({"group_key": "status"})

        output = {
            "count": 5,
            "cur_page": 1,
            "num_pages": 1,
            "groups": [
                {
                    "name": NODE_STATUS.NEW,
                    "value": NODE_STATUS.NEW,
                    "count": 2,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_new
                    ],
                },
                {
                    "name": NODE_STATUS.READY,
                    "value": NODE_STATUS.READY,
                    "count": 3,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_ready
                    ],
                },
            ],
        }
        self.assertEqual(output, result)

    def test_group_label(self):
        def get_group_label(key, value):
            if key == "status":
                return NODE_STATUS_CHOICES_DICT[value]

        nodes_ready = [
            factory.make_Node(status=NODE_STATUS.READY) for _ in range(3)
        ]
        nodes_new = [
            factory.make_Node(status=NODE_STATUS.NEW) for _ in range(2)
        ]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        handler._get_group_label = get_group_label
        result = handler.list({"group_key": "status"})

        output = {
            "count": 5,
            "cur_page": 1,
            "num_pages": 1,
            "groups": [
                {
                    "name": NODE_STATUS_CHOICES_DICT[NODE_STATUS.NEW],
                    "value": NODE_STATUS.NEW,
                    "count": 2,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_new
                    ],
                },
                {
                    "name": NODE_STATUS_CHOICES_DICT[NODE_STATUS.READY],
                    "value": NODE_STATUS.READY,
                    "count": 3,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_ready
                    ],
                },
            ],
        }
        self.assertEqual(output, result)

    def test_group_items_with_none(self):
        for _ in range(4):
            factory.make_Node(status=NODE_STATUS.READY, power_type=None)
        for _ in range(4):
            factory.make_Node(status=NODE_STATUS.READY, power_type="manual")
        handler = self.make_nodes_handler(fields=["hostname", "status"])

        # [MMM] M----
        result = handler.list(
            {
                "group_key": "bmc__power_type",
                "page_size": 3,
                "page_number": 1,
            }
        )
        self.assertEqual(1, len(result["groups"]))
        self.assertEqual("manual", result["groups"][0]["name"])
        self.assertEqual("manual", result["groups"][0]["value"])

        # [MMMM-] ---
        result = handler.list(
            {
                "group_key": "bmc__power_type",
                "page_size": 5,
                "page_number": 1,
            }
        )
        self.assertEqual(2, len(result["groups"]))
        self.assertEqual("manual", result["groups"][0]["name"])
        self.assertEqual("None", result["groups"][1]["name"])
        self.assertEqual(None, result["groups"][1]["value"])

        # MMM [M--] --
        result = handler.list(
            {
                "group_key": "bmc__power_type",
                "page_size": 3,
                "page_number": 2,
            }
        )
        self.assertEqual(2, len(result["groups"]))
        self.assertEqual("manual", result["groups"][0]["name"])
        self.assertEqual("None", result["groups"][1]["name"])
        self.assertEqual(None, result["groups"][1]["value"])

        # MMMM [----]
        result = handler.list(
            {
                "group_key": "bmc__power_type",
                "page_size": 4,
                "page_number": 2,
            }
        )
        self.assertEqual(1, len(result["groups"]))
        self.assertEqual("None", result["groups"][0]["name"])
        self.assertEqual(None, result["groups"][0]["value"])

        # MMMM- [---]
        result = handler.list(
            {
                "group_key": "bmc__power_type",
                "page_size": 5,
                "page_number": 2,
            }
        )
        self.assertEqual(1, len(result["groups"]))
        self.assertEqual("None", result["groups"][0]["name"])
        self.assertEqual(None, result["groups"][0]["value"])

    def test_group_suppresion(self):
        nodes_ready = [
            factory.make_Node(status=NODE_STATUS.READY) for _ in range(3)
        ]
        _ = [factory.make_Node(status=NODE_STATUS.NEW) for _ in range(2)]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list(
            {"group_key": "status", "group_collapsed": [NODE_STATUS.NEW]}
        )

        output = {
            "count": 5,
            "cur_page": 1,
            "num_pages": 1,
            "groups": [
                {
                    "name": NODE_STATUS.NEW,
                    "value": NODE_STATUS.NEW,
                    "count": 2,
                    "collapsed": True,
                    "items": [],
                },
                {
                    "name": NODE_STATUS.READY,
                    "value": NODE_STATUS.READY,
                    "count": 3,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_ready
                    ],
                },
            ],
        }
        self.assertEqual(output, result)

    def test_group_suppresion_out_of_scope(self):
        nodes_ready = [
            factory.make_Node(status=NODE_STATUS.READY) for _ in range(3)
        ]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list(
            {"group_key": "status", "group_collapsed": [NODE_STATUS.NEW]}
        )

        output = {
            "count": 3,
            "cur_page": 1,
            "num_pages": 1,
            "groups": [
                {
                    "name": NODE_STATUS.READY,
                    "value": NODE_STATUS.READY,
                    "count": 3,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_ready
                    ],
                }
            ],
        }
        self.assertEqual(output, result)

    def test_group_page_first(self):
        _ = [factory.make_Node(status=NODE_STATUS.READY) for _ in range(5)]
        nodes_new = [
            factory.make_Node(status=NODE_STATUS.NEW) for _ in range(5)
        ]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list(
            {
                "group_key": "status",
                "page_size": 3,
                "page_number": 1,
            }
        )

        output = {
            "count": 10,
            "cur_page": 1,
            "num_pages": 4,
            "groups": [
                {
                    "name": NODE_STATUS.NEW,
                    "value": NODE_STATUS.NEW,
                    "count": 5,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_new[:3]
                    ],
                },
            ],
        }
        self.assertEqual(output, result)

    def test_group_page_next(self):
        nodes_ready = [
            factory.make_Node(status=NODE_STATUS.READY) for _ in range(5)
        ]
        nodes_new = [
            factory.make_Node(status=NODE_STATUS.NEW) for _ in range(5)
        ]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list(
            {
                "group_key": "status",
                "page_size": 3,
                "page_number": 2,
            }
        )

        output = {
            "count": 10,
            "cur_page": 2,
            "num_pages": 4,
            "groups": [
                {
                    "name": NODE_STATUS.NEW,
                    "value": NODE_STATUS.NEW,
                    "count": 5,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_new[3:]
                    ],
                },
                {
                    "name": NODE_STATUS.READY,
                    "value": NODE_STATUS.READY,
                    "count": 5,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_ready[:1]
                    ],
                },
            ],
        }
        self.assertEqual(output, result)

    def test_group_page_last(self):
        nodes_ready = [
            factory.make_Node(status=NODE_STATUS.READY) for _ in range(5)
        ]
        _ = [factory.make_Node(status=NODE_STATUS.NEW) for _ in range(5)]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list(
            {
                "group_key": "status",
                "page_size": 3,
                "page_number": 4,
            }
        )

        output = {
            "count": 10,
            "cur_page": 4,
            "num_pages": 4,
            "groups": [
                {
                    "name": NODE_STATUS.READY,
                    "value": NODE_STATUS.READY,
                    "count": 5,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_ready[4:]
                    ],
                }
            ],
        }
        self.assertEqual(output, result)

    def test_group_page_suppresion_beginning(self):
        nodes_ready = [
            factory.make_Node(status=NODE_STATUS.READY) for _ in range(5)
        ]
        _ = [factory.make_Node(status=NODE_STATUS.DEPLOYED) for _ in range(5)]
        _ = [factory.make_Node(status=NODE_STATUS.NEW) for _ in range(5)]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list(
            {
                "group_key": "status",
                "group_collapsed": [NODE_STATUS.NEW],
                "page_size": 4,
                "page_number": 1,
            }
        )

        output = {
            "count": 15,
            "cur_page": 1,
            "num_pages": 3,
            "groups": [
                {
                    "name": NODE_STATUS.NEW,
                    "value": NODE_STATUS.NEW,
                    "count": 5,
                    "collapsed": True,
                    "items": [],
                },
                {
                    "name": NODE_STATUS.READY,
                    "value": NODE_STATUS.READY,
                    "count": 5,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_ready[:4]
                    ],
                },
            ],
        }
        self.assertEqual(output, result)

    def test_group_page_suppresion_next_page(self):
        _ = [factory.make_Node(status=NODE_STATUS.READY) for _ in range(5)]
        nodes_deployed = [
            factory.make_Node(status=NODE_STATUS.DEPLOYED) for _ in range(5)
        ]
        _ = [factory.make_Node(status=NODE_STATUS.NEW) for _ in range(5)]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list(
            {
                "group_key": "status",
                "group_collapsed": [NODE_STATUS.READY],
                "page_size": 5,
                "page_number": 2,
            }
        )

        output = {
            "count": 15,
            "cur_page": 2,
            "num_pages": 2,
            "groups": [
                {
                    "name": NODE_STATUS.READY,
                    "value": NODE_STATUS.READY,
                    "count": 5,
                    "collapsed": True,
                    "items": [],
                },
                {
                    "name": NODE_STATUS.DEPLOYED,
                    "value": NODE_STATUS.DEPLOYED,
                    "count": 5,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_deployed
                    ],
                },
            ],
        }
        self.assertEqual(output, result)

    def test_group_page_suppresion_middle(self):
        _ = [factory.make_Node(status=NODE_STATUS.READY) for _ in range(5)]
        nodes_deployed = [
            factory.make_Node(status=NODE_STATUS.DEPLOYED) for _ in range(5)
        ]
        nodes_new = [
            factory.make_Node(status=NODE_STATUS.NEW) for _ in range(5)
        ]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list(
            {
                "group_key": "status",
                "group_collapsed": [NODE_STATUS.READY],
                "page_size": 4,
                "page_number": 2,
            }
        )

        output = {
            "count": 15,
            "cur_page": 2,
            "num_pages": 3,
            "groups": [
                {
                    "name": NODE_STATUS.NEW,
                    "value": NODE_STATUS.NEW,
                    "count": 5,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_new[4:]
                    ],
                },
                {
                    "name": NODE_STATUS.READY,
                    "value": NODE_STATUS.READY,
                    "count": 5,
                    "collapsed": True,
                    "items": [],
                },
                {
                    "name": NODE_STATUS.DEPLOYED,
                    "value": NODE_STATUS.DEPLOYED,
                    "count": 5,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_deployed[:3]
                    ],
                },
            ],
        }
        self.assertEqual(output, result)

    def test_group_page_suppresion_end(self):
        nodes_ready = [
            factory.make_Node(status=NODE_STATUS.READY) for _ in range(5)
        ]
        _ = [factory.make_Node(status=NODE_STATUS.DEPLOYED) for _ in range(5)]
        _ = [factory.make_Node(status=NODE_STATUS.NEW) for _ in range(5)]

        handler = self.make_nodes_handler(fields=["hostname", "status"])
        result = handler.list(
            {
                "group_key": "status",
                "group_collapsed": [NODE_STATUS.DEPLOYED],
                "page_size": 4,
                "page_number": 3,
            }
        )

        output = {
            "count": 15,
            "cur_page": 3,
            "num_pages": 3,
            "groups": [
                {
                    "name": NODE_STATUS.READY,
                    "value": NODE_STATUS.READY,
                    "count": 5,
                    "collapsed": False,
                    "items": [
                        {"hostname": n.hostname, "status": n.status}
                        for n in nodes_ready[3:]
                    ],
                },
                {
                    "name": NODE_STATUS.DEPLOYED,
                    "value": NODE_STATUS.DEPLOYED,
                    "count": 5,
                    "collapsed": True,
                    "items": [],
                },
            ],
        }
        self.assertEqual(output, result)


class TestHandlerTransaction(
    MAASTransactionServerTestCase, FakeNodesHandlerMixin
):
    def test_execute_calls_asynchronous_method_with_params(self):
        # An asynchronous method -- decorated with @asynchronous -- is called
        # directly, not in a thread.
        handler = self.make_nodes_handler()
        handler.get = asynchronous(lambda params: succeed(sentinel.thing))
        params = {"system_id": factory.make_name("system_id")}
        result = handler.execute("get", params).wait(TIMEOUT)
        self.assertIs(result, sentinel.thing)

    def test_execute_calls_coroutine_method_with_params(self):
        # An asyncio coroutine method is called directly, not in a thread.
        async def my_get(params):
            return sentinel.thing

        handler = self.make_nodes_handler()
        handler.get = my_get
        params = {"system_id": factory.make_name("system_id")}
        result = handler.execute("get", params).wait(TIMEOUT)
        self.assertIs(result, sentinel.thing)
