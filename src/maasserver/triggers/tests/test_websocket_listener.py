# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import contextmanager
import logging
import random
from unittest import skip

from netaddr import IPAddress
from twisted.internet.defer import (
    CancelledError,
    DeferredList,
    DeferredQueue,
    inlineCallbacks,
)

from maasserver.enum import (
    BMC_TYPE,
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
    NODE_STATUS,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
)
from maasserver.listener import PostgresListenerService
from maasserver.models import ControllerInfo, Node, OwnerData, VMCluster
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partition import MIN_PARTITION_SIZE
from maasserver.storage_layouts import MIN_BOOT_PARTITION_SIZE
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import UserSkipCreateAuthorisationTokenFixture
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.triggers.testing import TransactionalHelpersMixin
from maasserver.triggers.websocket import node_fields
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from metadataserver.builtin_scripts import load_builtin_scripts
from metadataserver.enum import SCRIPT_STATUS
from provisioningserver.utils.snap import SnapVersionsInfo
from provisioningserver.utils.twisted import (
    asynchronous,
    DeferredValue,
    deferWithTimeout,
    FOREVER,
    synchronous,
)

wait_for_reactor = wait_for()


@synchronous
@contextmanager
def listenFor(channel):
    """Context manager to start and stop a listener service.

    The context object returned is a callable that returns a captured value.
    If you want to capture more than one value, call the callable more than
    once.

    Note that database changes MUST be committed for the listener to receive
    notifications. If you find that the returned callable times-out, consider
    if you've committed all changes to the database!

    A convenient way to deal with this is `MAASTransactionServerTestCase`
    which will mean you're running auto-commit by default.
    """
    listener = PostgresListenerService()
    values = DeferredQueue()

    def capture(*args):
        values.put(args)

    @asynchronous(timeout=10)
    def start():
        listener.register(channel, capture)
        return listener.startService()

    @asynchronous(timeout=10)
    def stop():
        return listener.stopService()

    @asynchronous(timeout=FOREVER)
    def get(timeout=2):
        return deferWithTimeout(timeout, values.get)

    start()
    try:
        yield get
    finally:
        stop()


class TestNodeListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers code."""

    scenarios = (
        (
            "machine",
            {
                "params": {
                    "node_type": NODE_TYPE.MACHINE,
                    # This is needed to avoid updating the node after creating it
                    "with_boot_disk": False,
                },
                "listener": "machine",
            },
        ),
        (
            "device",
            {"params": {"node_type": NODE_TYPE.DEVICE}, "listener": "device"},
        ),
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            node = yield deferToDatabase(self.create_node, self.params)
            yield dv.get(timeout=2)
            self.assertEqual(("create", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        node = yield deferToDatabase(self.create_node, self.params)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node,
                node.system_id,
                {"hostname": factory.make_name("hostname")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_description_update(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        node = yield deferToDatabase(self.create_node, self.params)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node,
                node.system_id,
                {"description": factory.make_name("hostname")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        node = yield deferToDatabase(self.create_node, self.params)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, node.system_id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_domain_name_change(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        domain = yield deferToDatabase(self.create_domain, {})
        params = self.params.copy()
        params["domain"] = domain
        yield deferToDatabase(self.create_node, params)
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_domain,
                domain.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_all_handler_on_domain_name_change(self):
        listener = self.make_listener_without_delay()
        dvs = DeferredValue()
        domain = yield deferToDatabase(self.create_domain, {})
        params = self.params.copy()
        params["domain"] = domain
        dvs = []
        nodes = set()
        for _ in range(3):
            node = yield deferToDatabase(self.create_node, params)
            nodes.add(node)
            dvs.append(DeferredValue())
        save_dvs = dvs[:]
        listener.register(self.listener, lambda *args: dvs.pop().set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_domain,
                domain.id,
                {"name": factory.make_name("name")},
            )
            results = yield DeferredList(dv.get(timeout=2) for dv in save_dvs)
            self.assertCountEqual(
                {("update", node.system_id) for node in nodes},
                {res for (suc, res) in results},
            )
        finally:
            yield listener.stopService()

    def test_expected_number_of_fields_watched(self):
        self.assertEqual(
            26,
            len(node_fields),
            "Any field listed here will be monitored for changes causing "
            "the UI on all clients to refresh this node object. This is "
            "costly! Only fields which are visible in the UI, and not listed "
            "in other handlers should be listed here.",
        )


class TestControllerListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers code."""

    scenarios = (
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    def set_version(self, controller, version):
        ControllerInfo.objects.set_version(controller, version)

    def set_versions_info(self, controller, versions_info):
        ControllerInfo.objects.set_versions_info(controller, versions_info)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_controllerinfo_insert(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        controller = yield deferToDatabase(self.create_node, self.params)
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.set_version, controller, "2.10.0")
            yield dv.get(timeout=2)
            self.assertEqual(("update", controller.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_controllerinfo_version_update(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        controller = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(self.set_version, controller, "2.10.0")
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.set_version, controller, "2.10.1")
            yield dv.get(timeout=2)
            self.assertEqual(("update", controller.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_controllerinfo_versionsinfo_update(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        controller = yield deferToDatabase(self.create_node, self.params)
        # first set the version
        yield deferToDatabase(self.set_version, controller, "3.0.0")
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            # update other fields but keep the same version
            yield deferToDatabase(
                self.set_versions_info,
                controller,
                SnapVersionsInfo(
                    current={"version": "3.0.0", "revision": "1234"}
                ),
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", controller.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_controllerinfo_delete(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        controller = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(self.set_version, controller, "2.10.0")
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(controller.controllerinfo.delete)
            yield dv.get(timeout=2)
            self.assertEqual(("update", controller.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        parent = yield deferToDatabase(self.create_node)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_node,
                {"node_type": NODE_TYPE.DEVICE, "parent": parent},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node,
                device.system_id,
                {"hostname": factory.make_name("hostname")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, device.system_id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestResourcePoolListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the resource pool
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            pool = yield deferToDatabase(self.create_resource_pool)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(pool.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        pool = yield deferToDatabase(self.create_resource_pool)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_resource_pool,
                pool.id,
                {"description": factory.make_name("description")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pool.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        pool = yield deferToDatabase(self.create_resource_pool)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_resource_pool, pool.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(pool.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_machine(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        pool = yield deferToDatabase(self.create_resource_pool)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_node,
                {"node_type": NODE_TYPE.MACHINE, "pool": pool},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pool.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_no_calls_handler_on_create_device(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_node, {"node_type": NODE_TYPE.DEVICE}
            )
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=0.2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_machine(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        pool = yield deferToDatabase(self.create_resource_pool)
        node = yield deferToDatabase(
            self.create_node, {"node_type": NODE_TYPE.MACHINE, "pool": pool}
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, node.system_id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pool.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_no_calls_handler_on_delete_device(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        machine = yield deferToDatabase(
            self.create_node, {"node_type": NODE_TYPE.DEVICE}
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, machine.system_id)
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=0.2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_machine_pool(self):
        listener = self.make_listener_without_delay()
        dvs = dv1, dv2 = [DeferredValue(), DeferredValue()]
        listener.register("resourcepool", lambda *args: dvs.pop(0).set(args))
        pool1 = yield deferToDatabase(self.create_resource_pool)
        pool2 = yield deferToDatabase(self.create_resource_pool)
        node = yield deferToDatabase(
            self.create_node, {"node_type": NODE_TYPE.MACHINE, "pool": pool1}
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node, node.system_id, {"pool": pool2}
            )
            yield dv1.get(timeout=2)
            yield dv2.get(timeout=2)
            values = sorted([dv1.value, dv2.value])
            pool_ids = sorted(str(pool.id) for pool in [pool1, pool2])
            self.assertEqual(("update", str(pool_ids[0])), values[0])
            self.assertEqual(("update", str(pool_ids[1])), values[1])
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_machine_status_to_ready(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        pool = yield deferToDatabase(self.create_resource_pool)
        initial_status = random.choice(
            [NODE_STATUS.COMMISSIONING, NODE_STATUS.RELEASING]
        )
        initial_status = NODE_STATUS.BROKEN
        node = yield deferToDatabase(
            self.create_node,
            {
                "node_type": NODE_TYPE.MACHINE,
                "status": initial_status,
                "pool": pool,
            },
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node, node.system_id, {"status": NODE_STATUS.READY}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pool.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_machine_status_from_ready(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        pool = yield deferToDatabase(self.create_resource_pool)
        node = yield deferToDatabase(
            self.create_node,
            {
                "node_type": NODE_TYPE.MACHINE,
                "status": NODE_STATUS.READY,
                "pool": pool,
            },
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node,
                node.system_id,
                {"status": NODE_STATUS.COMMISSIONING},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pool.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_machine_node_type_to_machine(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        pool = yield deferToDatabase(self.create_resource_pool)
        initial_node_type = random.choice(
            [
                node_type
                for node_type, _ in NODE_TYPE_CHOICES
                if node_type != NODE_TYPE.MACHINE
            ]
        )
        node = yield deferToDatabase(
            self.create_node, {"node_type": initial_node_type}
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node,
                node.system_id,
                {"node_type": NODE_TYPE.MACHINE, "pool": pool},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pool.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_machine_node_type_from_machine(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("resourcepool", lambda *args: dv.set(args))
        pool = yield deferToDatabase(self.create_resource_pool)
        new_node_type = random.choice(
            [
                node_type
                for node_type, _ in NODE_TYPE_CHOICES
                if node_type != NODE_TYPE.MACHINE
            ]
        )
        node = yield deferToDatabase(
            self.create_node,
            {"node_type": NODE_TYPE.MACHINE, "pool_id": pool.id},
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node,
                node.system_id,
                {"node_type": new_node_type, "pool_id": None},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pool.id)), dv.value)
        finally:
            yield listener.stopService()


class TestTagListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the tag
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("tag", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            tag = yield deferToDatabase(self.create_tag)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(tag.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("tag", lambda *args: dv.set(args))
        tag = yield deferToDatabase(self.create_tag)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_tag, tag.id, {"name": factory.make_name("tag")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(tag.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("tag", lambda *args: dv.set(args))
        tag = yield deferToDatabase(self.create_tag)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_tag, tag.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(tag.id)), dv.value)
        finally:
            yield listener.stopService()


class TestNodeTagListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_node_tags table."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
        (
            "device",
            {"params": {"node_type": NODE_TYPE.DEVICE}, "listener": "device"},
        ),
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        node_dv = DeferredValue()
        listener.register(self.listener, lambda *args: node_dv.set(args))
        tag_dv = DeferredValue()
        listener.register("tag", lambda *args: tag_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.add_node_to_tag, node, tag)
            yield node_dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), node_dv.value)
            yield tag_dv.get(timeout=2)
            self.assertEqual(("update", str(tag.id)), tag_dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        node = yield deferToDatabase(self.create_node, self.params)
        tag = yield deferToDatabase(self.create_tag)
        yield deferToDatabase(self.add_node_to_tag, node, tag)

        listener = self.make_listener_without_delay()
        node_dv = DeferredValue()
        tag_dv = DeferredValue()
        listener.register("tag", lambda *args: tag_dv.set(args))
        listener.register(self.listener, lambda *args: node_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.remove_node_from_tag, node, tag)
            yield node_dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), node_dv.value)
            yield tag_dv.get(timeout=2)
            self.assertEqual(("update", str(tag.id)), tag_dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_node_handler_with_update_on_tag_rename(self):
        node = yield deferToDatabase(self.create_node, self.params)
        tag = yield deferToDatabase(self.create_tag)
        yield deferToDatabase(self.add_node_to_tag, node, tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            tag = yield deferToDatabase(
                self.update_tag, tag.id, {"name": factory.make_name("tag")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestOwnerDataTriggers(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
        (
            "device",
            {"params": {"node_type": NODE_TYPE.DEVICE}, "listener": "device"},
        ),
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                OwnerData.objects.set_owner_data, node, {"foo": "baz"}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield deferToDatabase(
            OwnerData.objects.set_owner_data, node, {"foo": "bar"}
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                OwnerData.objects.set_owner_data, node, {"foo": "baz"}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_replace(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield deferToDatabase(
            OwnerData.objects.set_owner_data, node, {"foo": "bar"}
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                OwnerData.objects.set_owner_data, node, {"new": "value"}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestNodeMetadataTriggers(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_node_tags table."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
        (
            "device",
            {"params": {"node_type": NODE_TYPE.DEVICE}, "listener": "device"},
        ),
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.set_node_metadata, node, "foo", "bar")
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield deferToDatabase(self.set_node_metadata, node, "foo", "bar")
        yield listener.startService()
        try:
            yield deferToDatabase(self.set_node_metadata, node, "foo", "baz")
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield deferToDatabase(self.set_node_metadata, node, "foo", "bar")
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node_metadata, node, "foo")
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentTagListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_node_tags table."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.add_node_to_tag, device, tag)
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        tag = yield deferToDatabase(self.create_tag)
        yield deferToDatabase(self.add_node_to_tag, device, tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.remove_node_from_tag, device, tag)
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_node_handler_with_update_on_tag_rename(self):
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        tag = yield deferToDatabase(self.create_tag)
        yield deferToDatabase(self.add_node_to_tag, device, tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            tag = yield deferToDatabase(
                self.update_tag, tag.id, {"name": factory.make_name("tag")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestUserListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the user
    triggers code."""

    def setUp(self):
        super().setUp()
        self.useFixture(UserSkipCreateAuthorisationTokenFixture())

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            user = yield deferToDatabase(self.create_user)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(user.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        user = yield deferToDatabase(self.create_user)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_user,
                user.id,
                {"username": factory.make_name("username")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(user.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        user = yield deferToDatabase(self.create_user)

        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_user, user.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(user.id)), dv.value)
        finally:
            yield listener.stopService()


class TestEventListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the event
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("event", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            event = yield deferToDatabase(self.create_event)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(event.id)), dv.value)
        finally:
            yield listener.stopService()


class TestNodeEventListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_event table that notifies its node."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)
        event_type = yield deferToDatabase(
            self.create_event_type, {"level": logging.INFO}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_event, {"node": node, "type": event_type}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestNodeStaticIPAddressListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interfacestaticipaddresslink table that notifies its node."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE, "interface": True},
                "listener": "machine",
            },
        ),
        (
            "device",
            {
                "params": {"node_type": NODE_TYPE.DEVICE, "interface": True},
                "listener": "device",
            },
        ),
        (
            "rack",
            {
                "params": {
                    "node_type": NODE_TYPE.RACK_CONTROLLER,
                    "interface": True,
                },
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {
                    "node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                    "interface": True,
                },
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {
                    "node_type": NODE_TYPE.REGION_CONTROLLER,
                    "interface": True,
                },
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_staticipaddress, {"interface": interface}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )
        sip = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, sip.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentStaticIPAddressListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interfacestaticipaddresslink table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True}
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_staticipaddress, {"interface": interface}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True}
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id
        )
        sip = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, sip.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestScriptSetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_scriptset table that notifies its node."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
        (
            "device",
            {"params": {"node_type": NODE_TYPE.DEVICE}, "listener": "device"},
        ),
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        yield deferToDatabase(load_builtin_scripts)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_scriptset, node)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        yield deferToDatabase(load_builtin_scripts)
        node = yield deferToDatabase(self.create_node, self.params)
        result = yield deferToDatabase(self.create_scriptset, node)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_scriptset, result)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentScriptSetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_scriptset table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        yield deferToDatabase(load_builtin_scripts)
        device, parent = yield deferToDatabase(self.create_device_with_parent)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_scriptset, device)
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        yield deferToDatabase(load_builtin_scripts)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        result = yield deferToDatabase(self.create_scriptset, device)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_scriptset, result)
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestNDScriptResultListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_scriptresult table that notifies its node."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
        (
            "device",
            {"params": {"node_type": NODE_TYPE.DEVICE}, "listener": "device"},
        ),
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        yield deferToDatabase(load_builtin_scripts)
        node = yield deferToDatabase(self.create_node, self.params)
        script_set = yield deferToDatabase(self.create_scriptset, node)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_scriptresult, script_set)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        yield deferToDatabase(load_builtin_scripts)
        node = yield deferToDatabase(self.create_node, self.params)
        script_set = yield deferToDatabase(self.create_scriptset, node)
        script_result = yield deferToDatabase(
            self.create_scriptresult,
            script_set,
            {"status": SCRIPT_STATUS.PENDING},
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(script_result.store_result, 0)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        yield deferToDatabase(load_builtin_scripts)
        node = yield deferToDatabase(self.create_node, self.params)
        script_set = yield deferToDatabase(self.create_scriptset, node)
        script_result = yield deferToDatabase(
            self.create_scriptresult, script_set
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_scriptresult, script_result)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestScriptResultListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listers code and the triggers on
    the maasserver_scriptresult table that notifies the node-results
    websocket."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        yield deferToDatabase(load_builtin_scripts)
        node = yield deferToDatabase(self.create_node)
        script_set = yield deferToDatabase(self.create_scriptset, node)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("scriptresult", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            script_result = yield deferToDatabase(
                self.create_scriptresult, script_set
            )
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(script_result.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        yield deferToDatabase(load_builtin_scripts)
        node = yield deferToDatabase(self.create_node)
        script_set = yield deferToDatabase(self.create_scriptset, node)
        script_result = yield deferToDatabase(
            self.create_scriptresult,
            script_set,
            {"status": SCRIPT_STATUS.PENDING},
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("scriptresult", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(script_result.store_result, 0)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(script_result.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        yield deferToDatabase(load_builtin_scripts)
        node = yield deferToDatabase(self.create_node)
        script_set = yield deferToDatabase(self.create_scriptset, node)
        script_result = yield deferToDatabase(
            self.create_scriptresult, script_set
        )
        script_result_id = script_result.id

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("scriptresult", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_scriptresult, script_result)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(script_result_id)), dv.value)
        finally:
            yield listener.stopService()


class TestNodeInterfaceListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interface table that notifies its node."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
        (
            "device",
            {"params": {"node_type": NODE_TYPE.DEVICE}, "listener": "device"},
        ),
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_interface, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_interface, interface.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @skip("XXX: LaMontJones 2016-06-14 bug=1592474: Fails spuriously.")
    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_interface,
                interface.id,
                {"mac_address": factory.make_mac_address()},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_old_node_on_update(self):
        node1 = yield deferToDatabase(self.create_node, self.params)
        node2 = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node1}
        )
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = self.make_listener_without_delay()
        listener.register(self.listener, set_defer_value)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_interface,
                interface.id,
                {"node_config": node2.current_config},
            )
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertCountEqual(
                [
                    ("update", node1.system_id),
                    ("update", node2.system_id),
                ],
                [dvs[0].value, dvs[1].value],
            )
        finally:
            yield listener.stopService()


class TestDeviceWithParentInterfaceListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interface table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        device, parent = yield deferToDatabase(self.create_device_with_parent)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_interface, {"node": device})
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        interface = yield deferToDatabase(
            self.create_interface, {"node": device}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_interface, interface.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        interface = yield deferToDatabase(
            self.create_interface, {"node": device}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_interface,
                interface.id,
                {"mac_address": factory.make_mac_address()},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_old_node_on_update(self):
        device1, parent1 = yield deferToDatabase(
            self.create_device_with_parent
        )
        device2, parent2 = yield deferToDatabase(
            self.create_device_with_parent
        )
        interface = yield deferToDatabase(
            self.create_interface, {"node": device1}
        )
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = self.make_listener_without_delay()
        listener.register("machine", set_defer_value)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_interface,
                interface.id,
                {"node_config": device2.current_config},
            )
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertCountEqual(
                [
                    ("update", parent1.system_id),
                    ("update", parent2.system_id),
                ],
                [dvs[0].value, dvs[1].value],
            )
        finally:
            yield listener.stopService()


class TestFabricListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification_with_blank_name(self):
        listener = self.make_listener_without_delay()
        dvs = [DeferredValue(), DeferredValue()]
        save_dvs = dvs[:]
        listener.register("fabric", lambda *args: dvs.pop().set(args))
        yield listener.startService()
        try:
            fabric = yield deferToDatabase(self.create_fabric)
            results = yield DeferredList(dv.get(timeout=2) for dv in save_dvs)
            self.assertCountEqual(
                [("create", str(fabric.id)), ("update", str(fabric.id))],
                [res for (suc, res) in results],
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification_with_name(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("fabric", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            fabric = yield deferToDatabase(
                self.create_fabric, {"name": factory.make_name("name")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(fabric.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("fabric", lambda *args: dv.set(args))
        fabric = yield deferToDatabase(self.create_fabric)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_fabric,
                fabric.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(fabric.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("fabric", lambda *args: dv.set(args))
        fabric = yield deferToDatabase(self.create_fabric)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_fabric, fabric.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(fabric.id)), dv.value)
        finally:
            yield listener.stopService()


class TestVLANListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        fabric = yield deferToDatabase(self.create_fabric)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vlan", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            vlan = yield deferToDatabase(self.create_vlan, {"fabric": fabric})
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(vlan.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        fabric = yield deferToDatabase(self.create_fabric)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vlan", lambda *args: dv.set(args))
        vlan = yield deferToDatabase(self.create_vlan, {"fabric": fabric})

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_vlan, vlan.id, {"name": factory.make_name("name")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(vlan.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        fabric = yield deferToDatabase(self.create_fabric)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vlan", lambda *args: dv.set(args))
        vlan = yield deferToDatabase(self.create_vlan, {"fabric": fabric})
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_vlan, vlan.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(vlan.id)), dv.value)
        finally:
            yield listener.stopService()


class TestIPRangeListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("iprange", lambda *args: dv.set(args))
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(
            self.create_subnet, {"cidr": str(network)}
        )
        params = {
            "subnet": subnet,
            "start_ip": IPAddress(network.first + 2),
            "end_ip": IPAddress(network.last - 1),
        }
        yield listener.startService()
        try:
            iprange = yield deferToDatabase(self.create_iprange, params)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(iprange.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("iprange", lambda *args: dv.set(args))
        iprange = yield deferToDatabase(self.create_iprange)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_iprange,
                iprange.id,
                {"comment": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(iprange.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("iprange", lambda *args: dv.set(args))
        iprange = yield deferToDatabase(self.create_iprange)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_iprange, iprange.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(iprange.id)), dv.value)
        finally:
            yield listener.stopService()


class TestStaticRouteListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("staticroute", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            staticroute = yield deferToDatabase(self.create_staticroute)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(staticroute.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("staticroute", lambda *args: dv.set(args))
        staticroute = yield deferToDatabase(
            self.create_staticroute, {"metric": 9}
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticroute,
                staticroute.id,
                {"metric": random.randint(10, 500)},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(staticroute.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("staticroute", lambda *args: dv.set(args))
        staticroute = yield deferToDatabase(self.create_staticroute)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticroute, staticroute.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(staticroute.id)), dv.value)
        finally:
            yield listener.stopService()


class TestDomainListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            domain = yield deferToDatabase(self.create_domain)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        domain = yield deferToDatabase(self.create_domain)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_domain,
                domain.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        domain = yield deferToDatabase(self.create_domain)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_domain, domain.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_ip_address_update(self):
        domain = yield deferToDatabase(self.create_domain)
        params = {"node_type": NODE_TYPE.MACHINE, "domain": domain}
        node = yield deferToDatabase(self.create_node, params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node}
        )
        subnet = yield deferToDatabase(self.create_subnet)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "subnet": subnet,
                "ip": "",
            },
        )

        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress,
                ipaddress.id,
                {"alloc_type": IPADDRESS_TYPE.STICKY, "ip": selected_ip},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_node_ip_address_addition(self):
        domain = yield deferToDatabase(self.create_domain)
        params = {"node_type": NODE_TYPE.MACHINE, "domain": domain}
        node = yield deferToDatabase(self.create_node, params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node}
        )
        subnet = yield deferToDatabase(self.create_subnet)

        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_staticipaddress,
                {
                    "alloc_type": IPADDRESS_TYPE.STICKY,
                    "interface": interface,
                    "subnet": subnet,
                    "ip": selected_ip,
                },
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_node_ip_address_removal(self):
        domain = yield deferToDatabase(self.create_domain)
        params = {"node_type": NODE_TYPE.MACHINE, "domain": domain}
        node = yield deferToDatabase(self.create_node, params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node}
        )
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "alloc_type": IPADDRESS_TYPE.STICKY,
                "interface": interface,
                "subnet": subnet,
                "ip": selected_ip,
            },
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, ipaddress.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_dnsresource_create_notification(self):
        domain = yield deferToDatabase(self.create_domain)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dnsresource, {"domain": domain})
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_dnsresource_address_addition(self):
        domain = yield deferToDatabase(self.create_domain)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        dnsrr = yield deferToDatabase(
            self.create_dnsresource,
            {"domain": domain, "no_ip_addresses": True},
        )
        subnet = yield deferToDatabase(self.create_subnet)
        listener.register("domain", lambda *args: dv.set(args))

        yield listener.startService()
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        try:
            yield deferToDatabase(
                self.create_staticipaddress,
                {
                    "alloc_type": IPADDRESS_TYPE.STICKY,
                    "dnsresource": dnsrr,
                    "subnet": subnet,
                    "ip": selected_ip,
                },
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_dnsresource_address_removal(self):
        domain = yield deferToDatabase(self.create_domain)
        dnsrr = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        staticip = yield deferToDatabase(self.get_first_staticipaddress, dnsrr)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, staticip.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_dnsresource_update_notification(self):
        domain = yield deferToDatabase(self.create_domain)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        dnsrr = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        listener.register("domain", lambda *args: dv.set(args))

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_dnsresource,
                dnsrr.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_dnsresource_delete_notification(self):
        domain = yield deferToDatabase(self.create_domain)
        dnsrr = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dnsresource, dnsrr.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_dnsdata_create_notification(self):
        domain = yield deferToDatabase(self.create_domain)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dnsdata, {"domain": domain})
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_dnsdata_update_notification(self):
        domain = yield deferToDatabase(self.create_domain)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        dnsdata = yield deferToDatabase(
            self.create_dnsdata, {"domain": domain}
        )
        listener.register("domain", lambda *args: dv.set(args))

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_dnsdata,
                dnsdata.id,
                {"ttl": random.randint(100, 199)},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_dnsdata_delete_notification(self):
        domain = yield deferToDatabase(self.create_domain)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("domain", lambda *args: dv.set(args))
        dnsdata = yield deferToDatabase(
            self.create_dnsdata, {"domain": domain}
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dnsdata, dnsdata.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(domain.id)), dv.value)
        finally:
            yield listener.stopService()


class TestSubnetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            subnet = yield deferToDatabase(self.create_subnet)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(subnet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        subnet = yield deferToDatabase(self.create_subnet)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(subnet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification_for_vlan(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        subnet = yield deferToDatabase(self.create_subnet)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_vlan,
                subnet.vlan.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(subnet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        subnet = yield deferToDatabase(self.create_subnet)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(subnet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_ip_address_insert(self):
        node = yield deferToDatabase(
            self.create_node,
            {"node_type": NODE_TYPE.MACHINE, "interface": True},
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )
        subnet = yield deferToDatabase(self.create_subnet)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_staticipaddress,
                {
                    "alloc_type": IPADDRESS_TYPE.AUTO,
                    "interface": interface,
                    "subnet": subnet,
                    "ip": "",
                },
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(subnet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_ip_address_update(self):
        node = yield deferToDatabase(
            self.create_node,
            {"node_type": NODE_TYPE.MACHINE, "interface": True},
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "subnet": subnet,
                "ip": "",
            },
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, ipaddress.id, {"ip": selected_ip}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(subnet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_ip_address_delete(self):
        node = yield deferToDatabase(
            self.create_node,
            {"node_type": NODE_TYPE.MACHINE, "interface": True},
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )
        subnet = yield deferToDatabase(self.create_subnet)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "subnet": subnet,
                "ip": "",
            },
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, ipaddress.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(subnet.id)), dv.value)
        finally:
            yield listener.stopService()


class TestSpaceListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification_with_blank_name(self):
        listener = self.make_listener_without_delay()
        dvs = [DeferredValue(), DeferredValue()]
        save_dvs = dvs[:]
        listener.register("space", lambda *args: dvs.pop().set(args))
        yield listener.startService()
        try:
            space = yield deferToDatabase(self.create_space)
            results = yield DeferredList(dv.get(timeout=2) for dv in save_dvs)
            self.assertCountEqual(
                [("create", str(space.id)), ("update", str(space.id))],
                [res for (suc, res) in results],
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification_with_name(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("space", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            space = yield deferToDatabase(
                self.create_space, {"name": factory.make_name("name")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(space.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("space", lambda *args: dv.set(args))
        space = yield deferToDatabase(self.create_space)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_space,
                space.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(space.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("space", lambda *args: dv.set(args))
        space = yield deferToDatabase(self.create_space)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_space, space.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(space.id)), dv.value)
        finally:
            yield listener.stopService()


class TestNodeNetworkListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_fabric, maasserver_space, maasserver_subnet, and
    maasserver_vlan tables that notifies affected nodes."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE, "interface": True},
                "listener": "machine",
            },
        ),
        (
            "device",
            {
                "params": {"node_type": NODE_TYPE.DEVICE, "interface": True},
                "listener": "device",
            },
        ),
        (
            "rack",
            {
                "params": {
                    "node_type": NODE_TYPE.RACK_CONTROLLER,
                    "interface": True,
                },
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {
                    "node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                    "interface": True,
                },
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {
                    "node_type": NODE_TYPE.REGION_CONTROLLER,
                    "interface": True,
                },
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_iface_with_update_on_fabric_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )
        fabric = yield deferToDatabase(self.get_interface_fabric, interface.id)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_fabric,
                fabric.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_iface_with_update_on_vlan_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )
        vlan = yield deferToDatabase(self.get_interface_vlan, interface.id)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_vlan, vlan.id, {"name": factory.make_name("name")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_subnet_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )
        subnet = yield deferToDatabase(self.get_ipaddress_subnet, ipaddress.id)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_space_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )
        space = yield deferToDatabase(self.get_ipaddress_space, ipaddress.id)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_space,
                space.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_ip_address_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id
        )
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "subnet": subnet,
                "ip": "",
            },
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, ipaddress.id, {"ip": selected_ip}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestDeviceWithParentNetworkListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_fabric, maasserver_space, maasserver_subnet, and
    maasserver_vlan tables that notifies affected nodes."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_iface_with_update_on_fabric_update(self):
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True}
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id
        )
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )
        fabric = yield deferToDatabase(self.get_interface_fabric, interface.id)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_fabric,
                fabric.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_iface_with_update_on_vlan_update(self):
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True}
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id
        )
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )
        vlan = yield deferToDatabase(self.get_interface_vlan, interface.id)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_vlan, vlan.id, {"name": factory.make_name("name")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_subnet_update(self):
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True}
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id
        )
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )
        subnet = yield deferToDatabase(self.get_ipaddress_subnet, ipaddress.id)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_space_update(self):
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True}
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id
        )
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface}
        )
        space = yield deferToDatabase(self.get_ipaddress_space, ipaddress.id)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_space,
                space.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_ip_address_update(self):
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True}
        )
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id
        )
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "subnet": subnet,
                "ip": "",
            },
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, ipaddress.id, {"ip": selected_ip}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", parent.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestStaticIPAddressSubnetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_staticipaddress tables that notifies affected subnets."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_update_on_subnet(self):
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress,
            {"alloc_type": IPADDRESS_TYPE.AUTO, "subnet": subnet, "ip": ""},
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, ipaddress.id, {"ip": selected_ip}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(subnet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_update_on_old_and_new_subnet(self):
        old_subnet = yield deferToDatabase(self.create_subnet)
        new_subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(new_subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "subnet": old_subnet,
                "ip": "",
            },
        )
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = self.make_listener_without_delay()
        listener.register("subnet", set_defer_value)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress,
                ipaddress.id,
                {"ip": selected_ip, "subnet": new_subnet},
            )
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertCountEqual(
                [
                    ("update", str(old_subnet.id)),
                    ("update", str(new_subnet.id)),
                ],
                [dvs[0].value, dvs[1].value],
            )
        finally:
            yield listener.stopService()


class TestMachineBlockDeviceListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_blockdevice, maasserver_physicalblockdevice, and
    maasserver_virtualblockdevice tables that notifies its machine."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_blockdevice, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_blockdevice, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_blockdevice, blockdevice.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_blockdevice, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_blockdevice,
                blockdevice.id,
                {"size": random.randint(MIN_BLOCK_DEVICE_SIZE, 1000**3)},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_physicalblockdevice_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_physicalblockdevice, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_physicalblockdevice,
                blockdevice.id,
                {"model": factory.make_name("model")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_virtualblockdevice_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_virtualblockdevice,
            {"node": node, "size": MIN_BOOT_PARTITION_SIZE},
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_virtualblockdevice,
                blockdevice.id,
                {"uuid": factory.make_UUID()},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestMachinePartitionTableListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_partitiontable tables that notifies its machine."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_partitiontable, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        node = yield deferToDatabase(self.create_node, self.params)
        partitiontable = yield deferToDatabase(
            self.create_partitiontable, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.delete_partitiontable, partitiontable.id
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        partitiontable = yield deferToDatabase(
            self.create_partitiontable, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            # No changes to apply, but trigger a save nonetheless.
            yield deferToDatabase(
                self.update_partitiontable,
                partitiontable.id,
                {},
                force_update=True,
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestMachinePartitionListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_partition tables that notifies its machine."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_partition, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_partition, partition.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @skip("XXX: GavinPanella 2016-03-11 bug=1556188: Fails spuriously.")
    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            # Only downsize the partition otherwise the test may fail due
            # to the random number being generated is greater than the mock
            # available disk space
            yield deferToDatabase(
                self.update_partition,
                partition.id,
                {"size": random.randint(MIN_PARTITION_SIZE, 1000**3)},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestMachineFilesystemListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_filesystem tables that notifies its machine."""

    scenarios = (
        (
            "machine",
            {"params": {"node_type": NODE_TYPE.MACHINE}, "channel": "machine"},
        ),
    )

    def setUp(self):
        super().setUp()

    def test_calls_handler_with_update_on_create_fs_on_partition(self):
        node = factory.make_Node(**self.params)
        partition = factory.make_Partition(node=node)
        with listenFor(self.channel) as get:
            factory.make_Filesystem(partition=partition)
            self.assertEqual(("update", node.system_id), get())

    def test_calls_handler_with_update_on_create_fs_on_block_device(self):
        node = factory.make_Node(**self.params)
        block_device = factory.make_BlockDevice(node=node)
        with listenFor(self.channel) as get:
            factory.make_Filesystem(block_device=block_device)
            self.assertEqual(("update", node.system_id), get())

    def test_calls_handler_with_update_on_create_special_fs(self):
        node = factory.make_Node(**self.params)
        with listenFor(self.channel) as get:
            factory.make_Filesystem(node_config=node.current_config)
            self.assertEqual(("update", node.system_id), get())

    def test_calls_handler_with_update_on_delete_fs_on_partition(self):
        node = factory.make_Node(**self.params)
        partition = factory.make_Partition(node=node)
        filesystem = factory.make_Filesystem(partition=partition)
        with listenFor(self.channel) as get:
            filesystem.delete()
            self.assertEqual(("update", node.system_id), get())

    def test_calls_handler_with_update_on_delete_fs_on_block_device(self):
        node = factory.make_Node(**self.params)
        block_device = factory.make_BlockDevice(node=node)
        filesystem = factory.make_Filesystem(block_device=block_device)
        with listenFor(self.channel) as get:
            filesystem.delete()
            self.assertEqual(("update", node.system_id), get())

    def test_calls_handler_with_update_on_delete_special_fs(self):
        node = factory.make_Node(**self.params)
        filesystem = factory.make_Filesystem(node_config=node.current_config)
        with listenFor(self.channel) as get:
            filesystem.delete()
            self.assertEqual(("update", node.system_id), get())

    def test_calls_handler_with_update_on_update_fs_on_partition(self):
        node = factory.make_Node(**self.params)
        partition = factory.make_Partition(node=node)
        filesystem = factory.make_Filesystem(partition=partition)
        with listenFor(self.channel) as get:
            filesystem.save(force_update=True)  # A no-op update is enough.
            self.assertEqual(("update", node.system_id), get())

    def test_calls_handler_with_update_on_update_fs_on_block_device(self):
        node = factory.make_Node(**self.params)
        block_device = factory.make_BlockDevice(node=node)
        filesystem = factory.make_Filesystem(block_device=block_device)
        with listenFor(self.channel) as get:
            filesystem.save(force_update=True)  # A no-op update is enough.
            self.assertEqual(("update", node.system_id), get())

    def test_calls_handler_with_update_on_update_special_fs(self):
        node = factory.make_Node(**self.params)
        filesystem = factory.make_Filesystem(node_config=node.current_config)
        with listenFor(self.channel) as get:
            filesystem.save(force_update=True)  # A no-op update is enough.
            self.assertEqual(("update", node.system_id), get())


class TestMachineFilesystemgroupListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_filesystemgroup tables that notifies its machine."""

    scenarios = (
        (
            "machine",
            {
                "params": {
                    "node_type": NODE_TYPE.MACHINE,
                    "with_boot_disk": True,
                },
                "listener": "machine",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(
            self.create_partitiontable, {"node": node, "bootable": True}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_filesystemgroup, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        node = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(
            self.create_partitiontable, {"node": node, "bootable": True}
        )
        filesystemgroup = yield deferToDatabase(
            self.create_filesystemgroup, {"node": node, "group_type": "raid-5"}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.delete_filesystemgroup, filesystemgroup.id
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(
            self.create_partitiontable, {"node": node, "bootable": True}
        )
        filesystemgroup = yield deferToDatabase(
            self.create_filesystemgroup, {"node": node, "group_type": "bcache"}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_filesystemgroup,
                filesystemgroup.id,
                {"name": factory.make_name("fsgroup")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestMachineCachesetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_cacheset tables that notifies its machine."""

    scenarios = (
        (
            "machine",
            {
                "params": {"node_type": NODE_TYPE.MACHINE},
                "listener": "machine",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_cacheset, {"node": node, "partition": partition}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node}
        )
        cacheset = yield deferToDatabase(
            self.create_cacheset, {"node": node, "partition": partition}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_cacheset, cacheset.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_update(self):
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node}
        )
        cacheset = yield deferToDatabase(
            self.create_cacheset, {"node": node, "partition": partition}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.startService()
        try:
            # No changes to apply, but trigger a save nonetheless.
            yield deferToDatabase(
                self.update_cacheset, cacheset.id, {}, force_update=True
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestUserTokenListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the piston3_token
    table that notifies its user."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_token, {"user": user})
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(user.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        user = yield deferToDatabase(self.create_user)
        token = yield deferToDatabase(self.create_token, {"user": user})

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_token, token.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(user.id)), dv.value)
        finally:
            yield listener.stopService()


class TestTokenListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the piston3_token
    table."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create(self):
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("token", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            obj = yield deferToDatabase(self.create_token, {"user": user})
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(obj.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update(self):
        user = yield deferToDatabase(self.create_user)
        token = yield deferToDatabase(self.create_token, {"user": user})
        new_name = factory.make_name("name")

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("token", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            # Force the update because the key contents could be the same.
            yield deferToDatabase(self.update_token, token.id, name=new_name)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(token.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete(self):
        user = yield deferToDatabase(self.create_user)
        token = yield deferToDatabase(self.create_token, {"user": user})

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("token", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_token, token.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(token.id)), dv.value)
        finally:
            yield listener.stopService()


class TestUserSSLKeyListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the maasserver_sslkey
    table that notifies its user."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_create(self):
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_sslkey, {"user": user})
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(user.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_with_update_on_delete(self):
        user = yield deferToDatabase(self.create_user)
        sslkey = yield deferToDatabase(self.create_sslkey, {"user": user})

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_sslkey, sslkey.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(user.id)), dv.value)
        finally:
            yield listener.stopService()


class TestSSLKeyListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the maasserver_sslkey
    table."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create(self):
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("sslkey", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            obj = yield deferToDatabase(self.create_sslkey, {"user": user})
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(obj.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update(self):
        user = yield deferToDatabase(self.create_user)
        sslkey = yield deferToDatabase(self.create_sslkey, {"user": user})
        other_sslkey = yield deferToDatabase(
            self.create_sslkey,
            {"user": user, "key_string": get_data("data/test_x509_1.pem")},
        )
        contents = other_sslkey.key
        yield deferToDatabase(self.delete_sslkey, other_sslkey.id)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("sslkey", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            # Force the update because the key contents could be the same.
            yield deferToDatabase(
                self.update_sslkey,
                sslkey.id,
                {"key": contents},
                force_update=True,
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(sslkey.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete(self):
        user = yield deferToDatabase(self.create_user)
        sslkey = yield deferToDatabase(self.create_sslkey, {"user": user})

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("sslkey", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_sslkey, sslkey.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(sslkey.id)), dv.value)
        finally:
            yield listener.stopService()


class TestDHCPSnippetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("dhcpsnippet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            snippet = yield deferToDatabase(self.create_dhcp_snippet)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(snippet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("dhcpsnippet", lambda *args: dv.set(args))
        snippet = yield deferToDatabase(self.create_dhcp_snippet)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_dhcp_snippet,
                snippet.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(snippet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("dhcpsnippet", lambda *args: dv.set(args))
        snippet = yield deferToDatabase(self.create_dhcp_snippet)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dhcp_snippet, snippet.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(snippet.id)), dv.value)
        finally:
            yield listener.stopService()


class TestPackageRepositoryListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("packagerepository", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            repository = yield deferToDatabase(self.create_package_repository)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(repository.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("packagerepository", lambda *args: dv.set(args))
        repository = yield deferToDatabase(self.create_package_repository)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_package_repository,
                repository.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(repository.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("packagerepository", lambda *args: dv.set(args))
        repository = yield deferToDatabase(self.create_package_repository)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.delete_package_repository, repository.id
            )
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(repository.id)), dv.value)
        finally:
            yield listener.stopService()


class TestIPRangeSubnetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_iprange tables that notifies affected subnets."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        subnet = yield deferToDatabase(
            self.create_subnet,
            {
                "cidr": "192.168.0.0/24",
                "gateway_ip": "192.168.0.1",
                "dns_servers": [],
            },
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            iprange = yield deferToDatabase(
                self.create_iprange,
                {
                    "alloc_type": IPRANGE_TYPE.DYNAMIC,
                    "subnet": subnet,
                    "start_ip": "192.168.0.100",
                    "end_ip": "192.168.0.110",
                },
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(iprange.subnet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        iprange = yield deferToDatabase(self.create_iprange)
        new_end_ip = factory.pick_ip_in_IPRange(
            iprange, but_not=[iprange.start_ip, iprange.end_ip]
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_iprange, iprange.id, {"end_ip": new_end_ip}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(iprange.subnet.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_on_old_and_new_subnet_notification(self):
        old_subnet = yield deferToDatabase(
            self.create_subnet,
            {
                "cidr": "192.168.0.0/24",
                "gateway_ip": "192.168.0.1",
                "dns_servers": [],
            },
        )
        new_subnet = yield deferToDatabase(
            self.create_subnet,
            {
                "cidr": "192.168.1.0/24",
                "gateway_ip": "192.168.1.1",
                "dns_servers": [],
            },
        )
        iprange = yield deferToDatabase(
            self.create_iprange,
            {
                "alloc_type": IPRANGE_TYPE.DYNAMIC,
                "subnet": old_subnet,
                "start_ip": "192.168.0.100",
                "end_ip": "192.168.0.110",
            },
        )
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = self.make_listener_without_delay()
        listener.register("subnet", set_defer_value)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_iprange,
                iprange.id,
                {
                    "type": IPRANGE_TYPE.DYNAMIC,
                    "subnet": new_subnet,
                    "start_ip": "192.168.1.10",
                    "end_ip": "192.168.1.150",
                },
            )
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertCountEqual(
                [
                    ("update", str(old_subnet.id)),
                    ("update", str(new_subnet.id)),
                ],
                [dvs[0].value, dvs[1].value],
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        iprange = yield deferToDatabase(self.create_iprange)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_iprange, iprange.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(iprange.subnet.id)), dv.value)
        finally:
            yield listener.stopService()


class TestBMCListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    scenarios = (
        (
            "machine",
            {
                "params": {
                    "node_type": NODE_TYPE.MACHINE,
                    # This is needed to avoid updating the node after creating it
                    "with_boot_disk": False,
                },
                "listener": "machine",
            },
        ),
        (
            "rack",
            {
                "params": {"node_type": NODE_TYPE.RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region_and_rack",
            {
                "params": {"node_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER},
                "listener": "controller",
            },
        ),
        (
            "region",
            {
                "params": {"node_type": NODE_TYPE.REGION_CONTROLLER},
                "listener": "controller",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_bmc_update(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        self.params.update(
            {
                "power_type": "lxd",
                "power_parameters": {"power_address": "1.2.3.4"},
            }
        )
        node = yield deferToDatabase(self.create_node, self.params)

        def update_node(system_id):
            node = Node.objects.get(system_id=system_id)
            node.bmc.set_power_parameters({"power_address": "5.6.7.8"})
            node.bmc.save()

        yield listener.startService()
        try:
            yield deferToDatabase(update_node, node.system_id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", node.system_id), dv.value)
        finally:
            yield listener.stopService()


class TestVMClusterListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    def create_vmcluster(self, values):
        return VMCluster.objects.create(**values)

    def update_vmcluster(self, filter, values):
        return VMCluster.objects.filter(**filter).update(**values)

    def delete_vmcluster(self, filter):
        VMCluster.objects.filter(**filter).delete()

    def create_clustered_node(self, cluster, **kwargs):
        vmhosts = cluster.hosts()
        vmhost = vmhosts[0]
        if "bmc" not in kwargs:
            kwargs["bmc"] = vmhost
        return Node.objects.create(**kwargs)

    def update_clustered_node(self, filter, cluster=None, **kwargs):
        if cluster is not None:
            vmhosts = cluster.hosts()
            vmhost = vmhosts[0]
            if "bmc" not in kwargs:
                kwargs["bmc"] = vmhost
        return Node.objects.filter(**filter).update(**kwargs)

    def remove_cluster_from_node(self, id):
        return Node.objects.filter(id=id).update(bmc=factory.make_Pod())

    def delete_clustered_node(self, id):
        Node.objects.filter(id=id).delete()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vmcluster", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            cluster = yield deferToDatabase(
                self.create_vmcluster,
                {
                    "name": factory.make_name("cluster"),
                    "project": factory.make_name("project"),
                },
            )
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(cluster.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        cluster = yield deferToDatabase(
            self.create_vmcluster,
            {
                "name": factory.make_name("cluster"),
                "project": factory.make_name("project"),
            },
        )
        listener.register("vmcluster", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            pool = yield deferToDatabase(factory.make_ResourcePool)
            yield deferToDatabase(
                self.update_vmcluster, {"id": cluster.id}, {"pool": pool}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(cluster.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        cluster = yield deferToDatabase(
            self.create_vmcluster,
            {
                "name": factory.make_name("cluster"),
                "project": factory.make_name("project"),
            },
        )
        listener.register("vmcluster", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_vmcluster, {"id": cluster.id})
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(cluster.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_node_insert_if_in_cluster(self):
        cluster = yield deferToDatabase(factory.make_VMCluster)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vmcluster", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_clustered_node,
                cluster,
                hostname=factory.make_name("hostname"),
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(cluster.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_node_update_old_and_new_cluster_same(self):
        cluster = yield deferToDatabase(factory.make_VMCluster)
        node = yield deferToDatabase(
            self.create_clustered_node,
            cluster,
            hostname=factory.make_name("hostname"),
        )
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vmcluster", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_clustered_node,
                {"id": node.id},
                hostname=factory.make_name("new_hostname"),
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(cluster.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_when_cluster_is_removed_from_node(self):
        cluster = yield deferToDatabase(factory.make_VMCluster)
        node = yield deferToDatabase(
            self.create_clustered_node,
            cluster,
            hostname=factory.make_name("hostname"),
        )
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vmcluster", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.remove_cluster_from_node, node.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(cluster.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_when_node_is_added_to_cluster(self):
        cluster = yield deferToDatabase(factory.make_VMCluster)
        node = yield deferToDatabase(factory.make_Node)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vmcluster", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_clustered_node, {"id": node.id}, cluster=cluster
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(cluster.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_twice_when_node_changes_clusters(self):
        cluster1 = yield deferToDatabase(factory.make_VMCluster)
        cluster2 = yield deferToDatabase(factory.make_VMCluster)
        node = yield deferToDatabase(
            self.create_clustered_node,
            cluster1,
            hostname=factory.make_name("hostname"),
        )
        listener = self.make_listener_without_delay()
        dvs = [DeferredValue() for _ in range(2)]

        def _check(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    return

        listener.register("vmcluster", _check)
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_clustered_node, {"id": node.id}, cluster=cluster2
            )
            notifies = []
            for dv in dvs:
                yield dv.get(timeout=2)
                notifies.append(dv.value)
            self.assertCountEqual(
                [("update", str(cluster1.id)), ("update", str(cluster2.id))],
                notifies,
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_when_node_in_cluster_is_deleted(self):
        cluster = yield deferToDatabase(factory.make_VMCluster)
        node = yield deferToDatabase(
            self.create_clustered_node,
            cluster,
            hostname=factory.make_name("hostname"),
        )
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vmcluster", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_clustered_node, node.id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(cluster.id)), dv.value)
        finally:
            yield listener.stopService()


class TestPodListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_bmc tables that notifies affected pods."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            pod = yield deferToDatabase(
                self.create_pod, {"name": factory.make_name("pod")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_same_bmc_types_notification(self):
        pod = yield deferToDatabase(
            self.create_pod, {"name": factory.make_name("pod")}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_pod, pod.id, {"name": factory.make_name("pod")}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_new_POD_bmc_type_notification(self):
        bmc = yield deferToDatabase(
            self.create_bmc, {"name": factory.make_name("bmc")}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_bmc, bmc.id, {"bmc_type": BMC_TYPE.POD}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(bmc.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_new_BMC_bmc_type_notification(self):
        pod = yield deferToDatabase(
            self.create_pod, {"name": factory.make_name("pod")}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_pod, pod.id, {"bmc_type": BMC_TYPE.BMC}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        pod = yield deferToDatabase(
            self.create_pod, {"name": factory.make_name("pod")}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_pod, pod.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_related_interface(self):
        pod, host = yield deferToDatabase(
            self.create_pod_with_host, {"name": factory.make_name("pod")}
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(lambda: factory.make_Interface(node=host))
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_related_interface(self):
        pod, host = yield deferToDatabase(
            self.create_pod_with_host, {"name": factory.make_name("pod")}
        )
        interface = yield deferToDatabase(
            lambda: factory.make_Interface(node=host)
        )

        def _change_vlan(interface):
            vlan2 = factory.make_VLAN()
            interface.vlan = vlan2
            interface.save()

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(_change_vlan, interface)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_interface_move(self):
        pod, host = yield deferToDatabase(
            self.create_pod_with_host, {"name": factory.make_name("pod")}
        )
        interface = yield deferToDatabase(
            lambda: factory.make_Interface(node=host)
        )

        def _change_interface_node(interface):
            node2 = factory.make_Node()
            interface.node_config = node2.current_config
            interface.save()

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(_change_interface_node, interface)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_interface_delete(self):
        pod, host = yield deferToDatabase(
            self.create_pod_with_host, {"name": factory.make_name("pod")}
        )
        interface = yield deferToDatabase(
            lambda: factory.make_Interface(node=host)
        )

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(interface.delete)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()


class TestNodePodListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_bmc tables that notifies affected pods."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        pod = yield deferToDatabase(self.create_pod)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_node, {"bmc": pod})
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        old_pod = yield deferToDatabase(
            self.create_pod, {"name": factory.make_name("pod")}
        )
        new_pod = yield deferToDatabase(
            self.create_pod, {"name": factory.make_name("pod")}
        )
        node = yield deferToDatabase(self.create_node, {"bmc": old_pod})
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = self.make_listener_without_delay()
        listener.register("pod", set_defer_value)
        yield listener.startService()
        try:

            @transactional
            def update_direct(system_id, pod_id):
                Node.objects.filter(system_id=system_id).update(bmc_id=pod_id)

            yield deferToDatabase(update_direct, node.system_id, new_pod.id)
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertCountEqual(
                [("update", str(old_pod.id)), ("update", str(new_pod.id))],
                [dvs[0].value, dvs[1].value],
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        pod = yield deferToDatabase(self.create_pod)
        node = yield deferToDatabase(self.create_node, {"bmc": pod})

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("pod", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, node.system_id)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(pod.id)), dv.value)
        finally:
            yield listener.stopService()


class TestNodeTypeChange(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of node type change triggers code."""

    scenarios = (
        (
            "machine_to_rack",
            {
                "from_type": NODE_TYPE.MACHINE,
                "from_listener": "machine",
                "to_type": NODE_TYPE.RACK_CONTROLLER,
                "to_listener": "controller",
            },
        ),
        (
            "machine_to_region",
            {
                "from_type": NODE_TYPE.MACHINE,
                "from_listener": "machine",
                "to_type": NODE_TYPE.REGION_CONTROLLER,
                "to_listener": "controller",
            },
        ),
        (
            "machine_to_rack_and_region",
            {
                "from_type": NODE_TYPE.MACHINE,
                "from_listener": "machine",
                "to_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                "to_listener": "controller",
            },
        ),
        (
            "machine_to_device",
            {
                "from_type": NODE_TYPE.MACHINE,
                "from_listener": "machine",
                "to_type": NODE_TYPE.DEVICE,
                "to_listener": "device",
            },
        ),
        (
            "rack_to_machine",
            {
                "from_type": NODE_TYPE.RACK_CONTROLLER,
                "from_listener": "controller",
                "to_type": NODE_TYPE.MACHINE,
                "to_listener": "machine",
            },
        ),
        (
            "rack_to_device",
            {
                "from_type": NODE_TYPE.RACK_CONTROLLER,
                "from_listener": "controller",
                "to_type": NODE_TYPE.DEVICE,
                "to_listener": "device",
            },
        ),
        (
            "region_to_machine",
            {
                "from_type": NODE_TYPE.REGION_CONTROLLER,
                "from_listener": "controller",
                "to_type": NODE_TYPE.MACHINE,
                "to_listener": "machine",
            },
        ),
        (
            "region_to_device",
            {
                "from_type": NODE_TYPE.REGION_CONTROLLER,
                "from_listener": "controller",
                "to_type": NODE_TYPE.DEVICE,
                "to_listener": "device",
            },
        ),
        (
            "region_and_rack_to_machine",
            {
                "from_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                "from_listener": "controller",
                "to_type": NODE_TYPE.MACHINE,
                "to_listener": "machine",
            },
        ),
        (
            "region_and_rack_to_device",
            {
                "from_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                "from_listener": "controller",
                "to_type": NODE_TYPE.DEVICE,
                "to_listener": "device",
            },
        ),
        (
            "device_to_rack",
            {
                "from_type": NODE_TYPE.DEVICE,
                "from_listener": "device",
                "to_type": NODE_TYPE.RACK_CONTROLLER,
                "to_listener": "controller",
            },
        ),
        (
            "device_to_region",
            {
                "from_type": NODE_TYPE.DEVICE,
                "from_listener": "device",
                "to_type": NODE_TYPE.REGION_CONTROLLER,
                "to_listener": "controller",
            },
        ),
        (
            "device_to_rack_and_region",
            {
                "from_type": NODE_TYPE.DEVICE,
                "from_listener": "device",
                "to_type": NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                "to_listener": "controller",
            },
        ),
        (
            "device_to_machine",
            {
                "from_type": NODE_TYPE.DEVICE,
                "from_listener": "device",
                "to_type": NODE_TYPE.MACHINE,
                "to_listener": "machine",
            },
        ),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_transition_notifies(self):
        listener1 = self.make_listener_without_delay()
        listener2 = self.make_listener_without_delay()
        node = yield deferToDatabase(
            self.create_node, {"node_type": self.from_type}
        )
        q_from, q_to = DeferredQueue(), DeferredQueue()
        listener1.register(self.from_listener, lambda *args: q_from.put(args))
        listener2.register(self.to_listener, lambda *args: q_to.put(args))
        yield listener1.startService()
        yield listener2.startService()
        try:
            node.node_type = self.to_type
            if self.to_type != NODE_TYPE.MACHINE:
                node.pool = None
            yield deferToDatabase(node.save)
            self.assertEqual(
                ("delete", node.system_id),
                (yield deferWithTimeout(2, q_from.get)),
            )
            if NODE_TYPE.MACHINE in (self.from_type, self.to_type):
                # Changing to and from a node will cause a pool to either
                # be added or removed. This causes an additional update
                # trigger.
                notifications = {}
                for _ in range(2):
                    f, system_id = yield deferWithTimeout(2, q_to.get)
                    notifications[f] = system_id
                self.assertDictEqual(
                    {"update": node.system_id, "create": node.system_id},
                    notifications,
                )
            else:
                self.assertEqual(
                    ("create", node.system_id),
                    (yield deferWithTimeout(2, q_to.get)),
                )
        finally:
            yield listener1.stopService()
            yield listener2.stopService()


class TestNotificationListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """Tests for notifications relating to the `Notification` model."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("notification", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            notification = yield deferToDatabase(factory.make_Notification)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(notification.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("notification", lambda *args: dv.set(args))
        notification = yield deferToDatabase(factory.make_Notification)

        def update_notification(notification):
            notification.users = not notification.users
            notification.admins = not notification.admins
            notification.save()

        yield listener.startService()
        try:
            yield deferToDatabase(update_notification, notification)
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(notification.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("notification", lambda *args: dv.set(args))
        notification = yield deferToDatabase(factory.make_Notification)
        notification_id = notification.id  # Capture before delete.
        yield listener.startService()
        try:
            yield deferToDatabase(notification.delete)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(notification_id)), dv.value)
        finally:
            yield listener.stopService()


class TestNotificationDismissalListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """Tests relating to the `NotificationDismissal` model.

    At present `NotificationDismissal` rows are only ever created.
    """

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("notificationdismissal", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            user = yield deferToDatabase(factory.make_User)
            notification = yield deferToDatabase(factory.make_Notification)
            yield deferToDatabase(notification.dismiss, user)
            yield dv.get(timeout=2)
            self.assertEqual(
                ("create", "%d:%d" % (notification.id, user.id)), dv.value
            )
        finally:
            yield listener.stopService()


class TestScriptListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        yield deferToDatabase(load_builtin_scripts)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("script", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            script = yield deferToDatabase(self.create_script)
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(script.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        yield deferToDatabase(load_builtin_scripts)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("script", lambda *args: dv.set(args))
        script = yield deferToDatabase(self.create_script)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_script,
                script.id,
                {"name": factory.make_name("name")},
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(script.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        yield deferToDatabase(load_builtin_scripts)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("script", lambda *args: dv.set(args))
        script = yield deferToDatabase(self.create_script)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_script, script.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(script.id)), dv.value)
        finally:
            yield listener.stopService()


class TestNodeDeviceListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_create_notification(self):
        node = yield deferToDatabase(self.create_node)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodedevice", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            node_device = yield deferToDatabase(
                self.create_node_device, {"node": node}
            )
            yield dv.get(timeout=2)
            self.assertEqual(("create", str(node_device.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_update_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodedevice", lambda *args: dv.set(args))
        node_device = yield deferToDatabase(self.create_node_device)

        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node_device,
                node_device.id,
                {
                    "commissioning_driver": factory.make_name(
                        "commissioning_driver"
                    )
                },
            )
            yield dv.get(timeout=2)
            self.assertEqual(("update", str(node_device.id)), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_delete_notification(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodedevice", lambda *args: dv.set(args))
        node_device = yield deferToDatabase(self.create_node_device)
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node_device, node_device.id)
            yield dv.get(timeout=2)
            self.assertEqual(("delete", str(node_device.id)), dv.value)
        finally:
            yield listener.stopService()
