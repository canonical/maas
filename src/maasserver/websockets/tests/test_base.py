# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.base`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from operator import attrgetter

from django.db.models.query import QuerySet
from maasserver.forms import (
    AdminNodeForm,
    AdminNodeWithMACAddressesForm,
)
from maasserver.models.node import Node
from maasserver.models.zone import Zone
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import (
    Handler,
    HandlerCache,
    HandlerDoesNotExistError,
    HandlerNoSuchMethodError,
    HandlerPKError,
    HandlerValidationError,
)
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import (
    MagicMock,
    sentinel,
)
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    MatchesStructure,
)


def make_handler(name, **kwargs):
    meta = type(b"Meta", (object,), kwargs)
    return object.__new__(
        type(name.encode("utf-8"), (Handler,), {"Meta": meta}))


class TestHandlerMeta(MAASTestCase):

    def test_creates_handler_with_default_meta(self):
        handler = Handler(None, {})
        self.assertThat(handler._meta, MatchesStructure(
            abstract=Is(False),
            allowed_methods=Equals(
                ["list", "get", "create", "update", "delete", "set_active"]),
            handler_name=Equals(""), object_class=Is(None), queryset=Is(None),
            pk=Equals("id"), fields=Is(None), exclude=Is(None),
            list_fields=Is(None), list_exclude=Is(None),
            non_changeable=Is(None), form=Is(None)))

    def test_creates_handler_with_options(self):
        handler = make_handler(
            "TestHandler", abstract=True, allowed_methods=["list"],
            handler_name="testing", queryset=Node.objects.all(),
            pk="system_id", fields=["hostname", "distro_series"],
            exclude=["system_id"], list_fields=["hostname"],
            list_exclude=["hostname"], non_changeable=["system_id"],
            form=sentinel.form)
        self.assertThat(handler._meta, MatchesStructure(
            abstract=Is(True), allowed_methods=Equals(["list"]),
            handler_name=Equals("testing"), object_class=Is(Node),
            queryset=IsInstance(QuerySet), pk=Equals("system_id"),
            fields=Equals(["hostname", "distro_series"]),
            exclude=Equals(["system_id"]), list_fields=Equals(["hostname"]),
            list_exclude=Equals(["hostname"]),
            non_changeable=Equals(["system_id"]),
            form=Is(sentinel.form)))

    def test_sets_handler_name_based_on_class_name(self):
        names = [
            ("TestHandler", "test"),
            ("TestHandlerNew", "testnew"),
            ("AlwaysLowerHandler", "alwayslower")
        ]
        for class_name, handler_name in names:
            obj = make_handler(class_name)
            self.expectThat(obj._meta.handler_name, Equals(handler_name))

    def test_sets_object_class_based_on_queryset(self):
        handler = make_handler(
            "TestHandler", queryset=Node.objects.all())
        self.assertIs(Node, handler._meta.object_class)

    def test_copy_fields_and_excludes_to_list_fields_and_list_excludes(self):
        fields = [factory.make_name("field") for _ in range(3)]
        exclude = [factory.make_name("field") for _ in range(3)]
        handler = make_handler(
            "TestHandler", fields=fields, exclude=exclude)
        self.assertEquals(fields, handler._meta.list_fields)
        self.assertEquals(exclude, handler._meta.list_exclude)

    def test_copy_fields_and_excludes_doesnt_overwrite_lists_if_set(self):
        fields = [factory.make_name("field") for _ in range(3)]
        exclude = [factory.make_name("field") for _ in range(3)]
        list_fields = [factory.make_name("field") for _ in range(3)]
        list_exclude = [factory.make_name("field") for _ in range(3)]
        handler = make_handler(
            "TestHandler", fields=fields, exclude=exclude,
            list_fields=list_fields, list_exclude=list_exclude)
        self.assertEquals(list_fields, handler._meta.list_fields)
        self.assertEquals(list_exclude, handler._meta.list_exclude)


class TestHandlerCache(MAASTestCase):

    def test_sets_cache_prefix(self):
        handler_name = factory.make_name("handler")
        backend_cache = {}
        cache = HandlerCache(handler_name, backend_cache)
        self.assertEquals("%s_" % handler_name, cache._cache_prefix)

    def test_sets_backend_cache(self):
        handler_name = factory.make_name("handler")
        backend_cache = {}
        cache = HandlerCache(handler_name, backend_cache)
        self.assertIs(backend_cache, cache._backend_cache)

    def test_len_only_counts_entries_for_handler(self):
        handler_name = factory.make_name("handler")
        cache_entry = "%s_key" % handler_name
        backend_cache = {
            "other": factory.make_name("other_value"),
            cache_entry: factory.make_name("value"),
            }
        cache = HandlerCache(handler_name, backend_cache)
        self.assertEquals(1, len(cache))

    def test_getitem_only_returns_entry_for_handler(self):
        handler_name = factory.make_name("handler")
        cache_entry = "%s_key" % handler_name
        value = factory.make_name("value")
        backend_cache = {
            cache_entry: value,
            }
        cache = HandlerCache(handler_name, backend_cache)
        self.assertEquals(value, cache["key"])

    def test_setitem_places_entry_in_backend_cache_with_prefix(self):
        handler_name = factory.make_name("handler")
        backend_cache = {}
        cache = HandlerCache(handler_name, backend_cache)
        value = factory.make_name("value")
        cache["key"] = value
        self.assertEquals(value, backend_cache["%s_key" % handler_name])

    def test_delitem_removes_entry_in_backend_cache_with_prefix(self):
        handler_name = factory.make_name("handler")
        cache_entry = "%s_key" % handler_name
        backend_cache = {
            cache_entry: factory.make_name("value"),
            }
        cache = HandlerCache(handler_name, backend_cache)
        del cache["key"]
        self.assertFalse(cache_entry in backend_cache)

    def test_get_calls_get_on_the_backend_with_prefix(self):
        handler_name = factory.make_name("handler")
        cache = HandlerCache(handler_name, MagicMock())
        default = factory.make_name("default")
        cache.get("key", default=default)
        self.assertThat(
            cache._backend_cache.get,
            MockCalledOnceWith("%s_key" % handler_name, default))


class TestHandler(MAASServerTestCase):

    def make_nodes_handler(self, **kwargs):
        kwargs["queryset"] = Node.objects.all()
        kwargs["object_class"] = Node
        kwargs["pk"] = "system_id"
        handler = make_handler("TestNodesHandler", **kwargs)
        handler.__init__(factory.make_User(), {})
        return handler

    def make_mock_node_with_fields(self, **kwargs):
        return object.__new__(
            type(b"MockNode", (object,), kwargs))

    def test_full_dehydrate_only_includes_allowed_fields(self):
        handler = self.make_nodes_handler(fields=["hostname", "power_type"])
        node = factory.make_Node()
        self.assertEquals({
            "hostname": node.hostname,
            "power_type": node.power_type,
            }, handler.full_dehydrate(node))

    def test_full_dehydrate_excludes_fields(self):
        handler = self.make_nodes_handler(
            fields=["hostname", "power_type"], exclude=["power_type"])
        node = factory.make_Node()
        self.assertEquals({
            "hostname": node.hostname,
            }, handler.full_dehydrate(node))

    def test_full_dehydrate_only_includes_list_fields_when_for_list(self):
        handler = self.make_nodes_handler(
            list_fields=["power_type", "power_state"])
        node = factory.make_Node()
        self.assertEquals({
            "power_type": node.power_type,
            "power_state": node.power_state,
            }, handler.full_dehydrate(node, for_list=True))

    def test_full_dehydrate_excludes_list_fields_when_for_list(self):
        handler = self.make_nodes_handler(
            list_fields=["power_type", "power_state"],
            list_exclude=["power_type"])
        node = factory.make_Node()
        self.assertEquals({
            "power_state": node.power_state,
            }, handler.full_dehydrate(node, for_list=True))

    def test_full_dehydrate_calls_field_dehydrate_method_if_exists(self):
        handler = self.make_nodes_handler(fields=["hostname"])
        mock_dehydrate_hostname = self.patch(
            handler, "dehydrate_hostname")
        mock_dehydrate_hostname.return_value = sentinel.hostname
        node = factory.make_Node()
        self.expectThat({
            "hostname": sentinel.hostname,
            }, Equals(handler.full_dehydrate(node)))
        self.expectThat(
            mock_dehydrate_hostname,
            MockCalledOnceWith(node.hostname))

    def test_full_dehydrate_calls_final_dehydrate_method(self):
        handler = self.make_nodes_handler(fields=["hostname"])
        mock_dehydrate = self.patch_autospec(handler, "dehydrate")
        mock_dehydrate.return_value = sentinel.final_dehydrate
        node = factory.make_Node()
        self.expectThat(
            sentinel.final_dehydrate, Equals(handler.full_dehydrate(node)))
        self.expectThat(
            mock_dehydrate,
            MockCalledOnceWith(
                node, {"hostname": node.hostname}, for_list=False))

    def test_dehydrate_does_nothing(self):
        handler = self.make_nodes_handler()
        self.assertEquals(
            sentinel.nothing,
            handler.dehydrate(sentinel.obj, sentinel.nothing))

    def test_full_hydrate_only_doesnt_set_primary_key_field(self):
        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(
            fields=["system_id", "hostname"])
        node = self.make_mock_node_with_fields(
            system_id=system_id,
            hostname=factory.make_name("hostname"))
        handler.full_hydrate(node, {
            "system_id": factory.make_name("system_id"),
            "hostname": hostname,
            })
        self.expectThat(system_id, Equals(node.system_id))
        self.expectThat(hostname, Equals(node.hostname))

    def test_full_hydrate_only_sets_allowed_fields(self):
        hostname = factory.make_name("hostname")
        power_state = "on"
        handler = self.make_nodes_handler(fields=["hostname", "power_state"])
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname"),
            power_state="off", power_type="ipmi")
        handler.full_hydrate(node, {
            "hostname": hostname,
            "power_state": power_state,
            "power_type": "etherwake",
            })
        self.expectThat(hostname, Equals(node.hostname))
        self.expectThat(power_state, Equals(node.power_state))
        self.expectThat("ipmi", Equals(node.power_type))

    def test_full_hydrate_only_sets_non_excluded_fields(self):
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(
            fields=["hostname", "power_state"], exclude=["power_state"])
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname"),
            power_state="off", power_type="ipmi")
        handler.full_hydrate(node, {
            "hostname": hostname,
            "power_state": "on",
            "power_type": "etherwake",
            })
        self.expectThat(hostname, Equals(node.hostname))
        self.expectThat("off", Equals(node.power_state))
        self.expectThat("ipmi", Equals(node.power_type))

    def test_full_hydrate_only_doesnt_set_fields_not_allowed_to_change(self):
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(
            fields=["hostname", "power_state"],
            non_changeable=["power_state"])
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname"),
            power_state="off", power_type="ipmi")
        handler.full_hydrate(node, {
            "hostname": hostname,
            "power_state": "on",
            "power_type": "etherwake",
            })
        self.expectThat(hostname, Equals(node.hostname))
        self.expectThat("off", Equals(node.power_state))
        self.expectThat("ipmi", Equals(node.power_type))

    def test_full_hydrate_calls_fields_hydrate_method_if_present(self):
        call_hostname = factory.make_name("hostname")
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(fields=["hostname"])
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname"))
        mock_hydrate_hostname = self.patch(handler, "hydrate_hostname")
        mock_hydrate_hostname.return_value = hostname
        handler.full_hydrate(node, {
            "hostname": call_hostname,
            })
        self.expectThat(hostname, Equals(node.hostname))
        self.expectThat(
            mock_hydrate_hostname, MockCalledOnceWith(call_hostname))

    def test_full_hydrate_calls_final_hydrate_method(self):
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(fields=["hostname"])
        node = self.make_mock_node_with_fields(
            hostname=factory.make_name("hostname"))
        mock_hydrate = self.patch_autospec(handler, "hydrate")
        mock_hydrate.return_value = sentinel.final_hydrate
        self.expectThat(
            sentinel.final_hydrate,
            Equals(
                handler.full_hydrate(node, {
                    "hostname": hostname,
                    })))
        self.expectThat(
            mock_hydrate,
            MockCalledOnceWith(
                node, {"hostname": hostname}))

    def test_hydrate_does_nothing(self):
        handler = self.make_nodes_handler()
        self.assertEquals(
            sentinel.obj,
            handler.hydrate(sentinel.obj, sentinel.nothing))

    def test_get_object_raises_HandlerPKError(self):
        handler = self.make_nodes_handler()
        self.assertRaises(
            HandlerPKError,
            handler.get_object, {"host": "test"})

    def test_get_object_raises_HandlerDoesNotExistError(self):
        handler = self.make_nodes_handler()
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get_object,
            {"system_id": factory.make_name("system_id")})

    def test_get_object_returns_object(self):
        handler = self.make_nodes_handler()
        node = factory.make_Node()
        self.assertEquals(
            node.hostname,
            handler.get_object(
                {"system_id": node.system_id}).hostname)

    def test_execute_only_allows_meta_allowed_methods(self):
        handler = self.make_nodes_handler(allowed_methods=['list'])
        self.assertRaises(
            HandlerNoSuchMethodError,
            handler.execute, "get", {})

    def test_execute_raises_HandlerNoSuchMethodError(self):
        handler = self.make_nodes_handler(allowed_methods=['extra_method'])
        self.assertRaises(
            HandlerNoSuchMethodError,
            handler.execute, "extra_method", {})

    def test_execute_calls_method_with_params(self):
        handler = self.make_nodes_handler()
        params = {
            "system_id": factory.make_name("system_id"),
            }
        mock_get = self.patch_autospec(handler, "get")
        handler.execute("get", params)
        self.assertThat(mock_get, MockCalledOnceWith(params))

    def test_list(self):
        output = [
            {"hostname": factory.make_Node().hostname}
            for _ in range(3)
            ]
        handler = self.make_nodes_handler(fields=['hostname'])
        self.assertItemsEqual(output, handler.list({}))

    def test_list_start(self):
        nodes = [
            factory.make_Node()
            for _ in range(6)
            ]
        nodes = sorted(nodes, key=attrgetter("system_id"))
        output = [
            {"hostname": node.hostname}
            for node in nodes[3:]
            ]
        handler = self.make_nodes_handler(fields=['hostname'])
        self.assertItemsEqual(
            output,
            handler.list({"start": nodes[2].system_id}))

    def test_list_limit(self):
        output = [
            {"hostname": factory.make_Node().hostname}
            for _ in range(3)
            ]
        for _ in range(3):
            factory.make_Node()
        handler = self.make_nodes_handler(fields=['hostname'])
        self.assertItemsEqual(output, handler.list({"limit": 3}))

    def test_list_start_and_limit(self):
        nodes = [
            factory.make_Node()
            for _ in range(9)
            ]
        nodes = sorted(nodes, key=attrgetter("system_id"))
        output = [
            {"hostname": node.hostname}
            for node in nodes[3:6]
            ]
        handler = self.make_nodes_handler(fields=['hostname'])
        self.assertItemsEqual(
            output, handler.list({"start": nodes[2].system_id, "limit": 3}))

    def test_list_adds_to_loaded_pks(self):
        pks = [
            factory.make_Node().system_id
            for _ in range(3)
            ]
        handler = self.make_nodes_handler(fields=['hostname'])
        handler.list({})
        self.assertItemsEqual(pks, handler.cache['loaded_pks'])

    def test_list_unions_the_loaded_pks(self):
        pks = [
            factory.make_Node().system_id
            for _ in range(3)
            ]
        handler = self.make_nodes_handler(fields=['hostname'])
        # Make two calls to list making sure the loaded_pks contains all of
        # the primary keys listed.
        handler.list({"limit": 1})
        handler.list({"start": pks[0]})
        self.assertItemsEqual(pks, handler.cache['loaded_pks'])

    def test_get(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler(fields=['hostname'])
        self.assertEquals(
            {"hostname": node.hostname},
            handler.get({"system_id": node.system_id}))

    def test_create_without_form(self):
        # Use a zone as its simple and easy to create without a form, unlike
        # Node which requires a form.
        handler = make_handler(
            "TestZoneHandler",
            queryset=Zone.objects.all(), fields=['name', 'description'])
        name = factory.make_name("zone")
        json_obj = handler.create({"name": name})
        self.expectThat({
            "name": name,
            "description": "",
            }, Equals(json_obj))
        self.expectThat(name, Equals(Zone.objects.get(name=name).name))

    def test_create_with_form_creates_node(self):
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        nodegroup = factory.make_NodeGroup()
        handler = self.make_nodes_handler(
            fields=['hostname', 'architecture'],
            form=AdminNodeWithMACAddressesForm)
        json_obj = handler.create({
            "hostname": hostname,
            "architecture": arch,
            "mac_addresses": [factory.make_mac_address()],
            "nodegroup": nodegroup.uuid,
            })
        self.expectThat({
            "hostname": hostname,
            "architecture": arch,
            }, Equals(json_obj))

    def test_create_with_form_uses_form_from_get_form_class(self):
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        nodegroup = factory.make_NodeGroup()
        handler = self.make_nodes_handler(
            fields=['hostname', 'architecture'])
        self.patch(
            handler,
            "get_form_class").return_value = AdminNodeWithMACAddressesForm
        json_obj = handler.create({
            "hostname": hostname,
            "architecture": arch,
            "mac_addresses": [factory.make_mac_address()],
            "nodegroup": nodegroup.uuid,
            })
        self.expectThat({
            "hostname": hostname,
            "architecture": arch,
            }, Equals(json_obj))

    def test_create_with_form_passes_request_with_user_set(self):
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        mock_form = MagicMock()
        mock_form.return_value.is_valid.return_value = True
        mock_form.return_value.save.return_value = factory.make_Node()
        handler = self.make_nodes_handler(fields=[], form=mock_form)
        handler.create({
            "hostname": hostname,
            "architecture": arch,
            })
        # Extract the passed request.
        passed_request = mock_form.call_args_list[0][1]['request']
        self.assertIs(handler.user, passed_request.user)

    def test_create_with_form_raises_HandlerValidationError(self):
        hostname = factory.make_name("hostname")
        arch = make_usable_architecture(self)
        handler = self.make_nodes_handler(
            fields=['hostname', 'architecture'],
            form=AdminNodeWithMACAddressesForm)
        self.assertRaises(
            HandlerValidationError, handler.create, {
                "hostname": hostname,
                "architecture": arch,
                })

    def test_update_without_form(self):
        handler = self.make_nodes_handler(fields=['hostname'])
        node = factory.make_Node()
        hostname = factory.make_name("hostname")
        json_obj = handler.update({
            "system_id": node.system_id,
            "hostname": hostname,
            })
        self.expectThat({
            "hostname": hostname,
            }, Equals(json_obj))
        self.expectThat(
            reload_object(node).hostname, Equals(hostname))

    def test_update_with_form_updates_node(self):
        arch = make_usable_architecture(self)
        node = factory.make_Node(architecture=arch)
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(
            fields=['hostname'], form=AdminNodeForm)
        json_obj = handler.update({
            "system_id": node.system_id,
            "hostname": hostname,
            })
        self.expectThat({
            "hostname": hostname,
            }, Equals(json_obj))
        self.expectThat(
            reload_object(node).hostname, Equals(hostname))

    def test_update_with_form_uses_form_from_get_form_class(self):
        arch = make_usable_architecture(self)
        node = factory.make_Node(architecture=arch)
        hostname = factory.make_name("hostname")
        handler = self.make_nodes_handler(fields=['hostname'])
        self.patch(
            handler,
            "get_form_class").return_value = AdminNodeForm
        json_obj = handler.update({
            "system_id": node.system_id,
            "hostname": hostname,
            })
        self.expectThat({
            "hostname": hostname,
            }, Equals(json_obj))
        self.expectThat(
            reload_object(node).hostname, Equals(hostname))

    def test_delete_deletes_object(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler()
        handler.delete({"system_id": node.system_id})
        self.assertIsNone(reload_object(node))

    def test_set_active_does_nothing_if_no_active_obj_and_missing_pk(self):
        handler = self.make_nodes_handler()
        mock_get = self.patch(handler, "get")
        handler.set_active({})
        self.assertThat(mock_get, MockNotCalled())

    def test_set_active_clears_active_if_missing_pk(self):
        handler = self.make_nodes_handler()
        handler.cache["active_pk"] = factory.make_name("system_id")
        handler.set_active({})
        self.assertFalse("active_pk" in handler.cache)

    def test_set_active_returns_data_and_sets_active(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler(fields=['system_id'])
        node_data = handler.set_active({"system_id": node.system_id})
        self.expectThat(node_data["system_id"], Equals(node.system_id))
        self.expectThat(handler.cache["active_pk"], Equals(node.system_id))

    def test_on_listen_calls_listen(self):
        handler = self.make_nodes_handler()
        mock_listen = self.patch(handler, "listen")
        mock_listen.side_effect = HandlerDoesNotExistError()
        handler.on_listen(sentinel.channel, sentinel.action, sentinel.pk)
        self.assertThat(
            mock_listen,
            MockCalledOnceWith(
                sentinel.channel, sentinel.action, sentinel.pk))

    def test_on_listen_returns_None_if_unknown_action(
            self):
        handler = self.make_nodes_handler()
        mock_listen = self.patch(handler, "listen")
        mock_listen.side_effect = HandlerDoesNotExistError()
        self.assertIsNone(
            handler.on_listen(
                sentinel.channel, factory.make_name("action"), sentinel.pk))

    def test_on_listen_delete_removes_pk_from_loaded(self):
        handler = self.make_nodes_handler()
        node = factory.make_Node()
        handler.cache["loaded_pks"].add(node.system_id)
        self.assertEquals(
            (handler._meta.handler_name, "delete", node.system_id),
            handler.on_listen(
                sentinel.channel, "delete", node.system_id))
        self.assertTrue(
            node.system_id not in handler.cache["loaded_pks"],
            "on_listen delete did not remove system_id from loaded_pks")

    def test_on_listen_delete_returns_None_if_pk_not_in_loaded(self):
        handler = self.make_nodes_handler()
        node = factory.make_Node()
        self.assertEquals(
            None,
            handler.on_listen(
                sentinel.channel, "delete", node.system_id))

    def test_on_listen_create_adds_pk_to_loaded(self):
        handler = self.make_nodes_handler(fields=['hostname'])
        node = factory.make_Node(owner=handler.user)
        self.assertEquals(
            (
                handler._meta.handler_name,
                "create",
                {"hostname": node.hostname}
            ),
            handler.on_listen(sentinel.channel, "create", node.system_id))
        self.assertTrue(
            node.system_id in handler.cache["loaded_pks"],
            "on_listen create did not add system_id to loaded_pks")

    def test_on_listen_update_returns_delete_action_if_obj_is_None(self):
        handler = self.make_nodes_handler()
        node = factory.make_Node()
        handler.cache["loaded_pks"].add(node.system_id)
        self.patch(handler, "listen").return_value = None
        self.assertEquals(
            (handler._meta.handler_name, "delete", node.system_id),
            handler.on_listen(
                sentinel.channel, "update", node.system_id))
        self.assertTrue(
            node.system_id not in handler.cache["loaded_pks"],
            "on_listen update did not remove system_id from loaded_pks")

    def test_on_listen_update_returns_update_action_if_obj_not_None(self):
        handler = self.make_nodes_handler(fields=['hostname'])
        node = factory.make_Node()
        handler.cache["loaded_pks"].add(node.system_id)
        self.assertEquals(
            (
                handler._meta.handler_name,
                "update",
                {"hostname": node.hostname},
            ),
            handler.on_listen(
                sentinel.channel, "update", node.system_id))
        self.assertTrue(
            node.system_id in handler.cache["loaded_pks"],
            "on_listen update removed system_id from loaded_pks")

    def test_on_listen_update_returns_create_action_if_not_in_loaded(self):
        handler = self.make_nodes_handler(fields=['hostname'])
        node = factory.make_Node()
        self.assertEquals(
            (
                handler._meta.handler_name,
                "create",
                {"hostname": node.hostname},
            ),
            handler.on_listen(
                sentinel.channel, "update", node.system_id))
        self.assertTrue(
            node.system_id in handler.cache["loaded_pks"],
            "on_listen update didnt add system_id to loaded_pks")

    def test_on_listen_update_call_full_dehydrate_for_list_if_not_active(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler()
        handler.cache["loaded_pks"].add(node.system_id)
        mock_dehydrate = self.patch(handler, "full_dehydrate")
        mock_dehydrate.return_value = sentinel.data
        self.expectThat(
            handler.on_listen(
                sentinel.channel, "update", node.system_id),
            Equals((handler._meta.handler_name, "update", sentinel.data)))
        self.expectThat(
            mock_dehydrate,
            MockCalledOnceWith(node, for_list=True))

    def test_on_listen_update_call_full_dehydrate_not_for_list_if_active(self):
        node = factory.make_Node()
        handler = self.make_nodes_handler()
        handler.cache["loaded_pks"].add(node.system_id)
        handler.cache["active_pk"] = node.system_id
        mock_dehydrate = self.patch(handler, "full_dehydrate")
        mock_dehydrate.return_value = sentinel.data
        self.expectThat(
            handler.on_listen(
                sentinel.channel, "update", node.system_id),
            Equals((handler._meta.handler_name, "update", sentinel.data)))
        self.expectThat(
            mock_dehydrate,
            MockCalledOnceWith(node, for_list=False))

    def test_listen_calls_get_object_with_pk_on_other_actions(self):
        handler = self.make_nodes_handler()
        mock_get_object = self.patch(handler, "get_object")
        mock_get_object.return_value = sentinel.obj
        self.expectThat(
            handler.listen(sentinel.channel, "update", sentinel.pk),
            Equals(sentinel.obj))
        self.expectThat(
            mock_get_object,
            MockCalledOnceWith({handler._meta.pk: sentinel.pk}))
