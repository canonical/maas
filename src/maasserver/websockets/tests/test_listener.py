# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.listner`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import namedtuple
import errno
import random

from crochet import wait_for_reactor
from django.contrib.auth.models import User
from django.db import connection
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
)
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cacheset import CacheSet
from maasserver.models.event import Event
from maasserver.models.fabric import Fabric
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.interface import Interface
from maasserver.models.node import Node
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.models.partition import Partition
from maasserver.models.partitiontable import PartitionTable
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.space import Space
from maasserver.models.sshkey import SSHKey
from maasserver.models.sslkey import SSLKey
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.models.tag import Tag
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.models.vlan import VLAN
from maasserver.models.zone import Zone
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.triggers import register_all_triggers
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets import listener as listener_module
from maasserver.websockets.listener import (
    PostgresListener,
    PostgresListenerNotifyError,
)
from maastesting.djangotestcase import DjangoTransactionTestCase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCalledWith,
    MockNotCalled,
)
from metadataserver.models import NodeResult
from mock import (
    ANY,
    sentinel,
)
from provisioningserver.utils.twisted import DeferredValue
from psycopg2 import OperationalError
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    Not,
)
from twisted.internet import (
    error,
    reactor,
)
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    inlineCallbacks,
)
from twisted.python.failure import Failure


FakeNotify = namedtuple("FakeNotify", ["channel", "payload"])


class TestPostgresListener(MAASServerTestCase):

    @transactional
    def send_notification(self, event, obj_id):
        cursor = connection.cursor()
        cursor.execute("NOTIFY %s, '%s';" % (event, obj_id))
        cursor.close()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_notification(self):
        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.send_notification, "node_create", 1)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '1'), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_connects_to_database(self):
        listener = PostgresListener()

        yield listener.tryConnection()
        try:
            self.assertTrue(listener.connected())
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_logs_error(self):
        listener = PostgresListener()

        exception_type = factory.make_exception_type()
        exception_message = factory.make_name("message")

        startConnection = self.patch(listener, "startConnection")
        startConnection.side_effect = exception_type(exception_message)
        mock_logMsg = self.patch(listener, "logMsg")

        with ExpectedException(exception_type):
            yield listener.tryConnection()

        self.assertThat(
            mock_logMsg,
            MockCalledOnceWith(
                format="Unable to connect to database: %(error)s",
                error=exception_message))

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_will_retry_in_3_seconds_if_autoReconnect_set(self):
        listener = PostgresListener()
        listener.autoReconnect = True

        startConnection = self.patch(listener, "startConnection")
        startConnection.side_effect = factory.make_exception()
        deferLater = self.patch(listener_module, "deferLater")
        deferLater.return_value = sentinel.retry

        result = yield listener.tryConnection()

        self.assertThat(result, Is(sentinel.retry))
        self.assertThat(deferLater, MockCalledWith(reactor, 3, ANY))

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_will_not_retry_if_autoReconnect_not_set(self):
        listener = PostgresListener()
        listener.autoReconnect = False

        exception_type = factory.make_exception_type()
        exception_message = factory.make_name("message")

        startConnection = self.patch(listener, "startConnection")
        startConnection.side_effect = exception_type(exception_message)
        deferLater = self.patch(listener_module, "deferLater")
        deferLater.return_value = sentinel.retry

        with ExpectedException(exception_type):
            yield listener.tryConnection()

        self.assertThat(deferLater, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test__stopping_cancels_start(self):
        listener = PostgresListener()

        # Start then stop immediately, without waiting for start to complete.
        starting = listener.start()
        starting_spy = DeferredValue()
        starting_spy.observe(starting)
        stopping = listener.stop()

        # Both `starting` and `stopping` have callbacks yet to fire.
        self.assertThat(starting.callbacks, Not(Equals([])))
        self.assertThat(stopping.callbacks, Not(Equals([])))

        # Wait for the listener to stop.
        yield stopping

        # Neither `starting` nor `stopping` have callbacks. This is because
        # `stopping` chained itself onto the end of `starting`.
        self.assertThat(starting.callbacks, Equals([]))
        self.assertThat(stopping.callbacks, Equals([]))

        # Confirmation that `starting` was cancelled.
        with ExpectedException(CancelledError):
            yield starting_spy.get()

    @wait_for_reactor
    def test__multiple_starts_return_same_Deferred(self):
        listener = PostgresListener()
        self.assertThat(listener.start(), Is(listener.start()))
        return listener.stop()

    @wait_for_reactor
    def test__multiple_stops_return_same_Deferred(self):
        listener = PostgresListener()
        self.assertThat(listener.stop(), Is(listener.stop()))
        return listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_calls_registerChannels_after_startConnection(self):
        listener = PostgresListener()

        exception_type = factory.make_exception_type()

        self.patch(listener, "startConnection")
        mock_registerChannels = self.patch(listener, "registerChannels")
        mock_registerChannels.side_effect = exception_type

        with ExpectedException(exception_type):
            yield listener.tryConnection()

        self.assertThat(
            mock_registerChannels,
            MockCalledOnceWith())

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_adds_self_to_reactor(self):
        listener = PostgresListener()

        # Spy on calls to reactor.addReader.
        self.patch(reactor, "addReader").side_effect = reactor.addReader

        yield listener.tryConnection()
        try:
            self.assertThat(
                reactor.addReader,
                MockCalledOnceWith(listener))
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_closes_connection_on_failure(self):
        listener = PostgresListener()

        exc_type = factory.make_exception_type()
        startReading = self.patch(listener, "startReading")
        startReading.side_effect = exc_type("no reason")

        with ExpectedException(exc_type):
            yield listener.tryConnection()

        self.assertThat(listener.connection, Is(None))

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_logs_success(self):
        listener = PostgresListener()

        mock_logMsg = self.patch(listener, "logMsg")
        yield listener.tryConnection()
        try:
            self.assertThat(
                mock_logMsg,
                MockCalledOnceWith("Listening for database notifications."))
        finally:
            yield listener.stop()

    @wait_for_reactor
    def test__connectionLost_logs_reason(self):
        listener = PostgresListener()
        self.patch(listener, "logErr")

        failure = Failure(factory.make_exception())

        listener.connectionLost(failure)

        self.assertThat(
            listener.logErr, MockCalledOnceWith(
                failure, "Connection lost."))

    @wait_for_reactor
    def test__connectionLost_does_not_log_reason_when_lost_cleanly(self):
        listener = PostgresListener()
        self.patch(listener, "logErr")

        listener.connectionLost(Failure(error.ConnectionDone()))

        self.assertThat(listener.logErr, MockNotCalled())

    def test_register_adds_channel_and_handler(self):
        listener = PostgresListener()
        channel = factory.make_name("channel")
        listener.register(channel, sentinel.handler)
        self.assertEqual(
            [sentinel.handler], listener.listeners[channel])

    def test__convertChannel_raises_exception_if_not_valid_channel(self):
        listener = PostgresListener()
        self.assertRaises(
            PostgresListenerNotifyError,
            listener.convertChannel, "node_create")

    def test__convertChannel_raises_exception_if_not_valid_action(self):
        listener = PostgresListener()
        self.assertRaises(
            PostgresListenerNotifyError,
            listener.convertChannel, "node_unknown")

    @wait_for_reactor
    @inlineCallbacks
    def test__doRead_removes_self_from_reactor_on_error(self):
        listener = PostgresListener()

        connection = self.patch(listener, "connection")
        connection.connection.poll.side_effect = OperationalError()

        self.patch(reactor, "removeReader")
        self.patch(listener, "connectionLost")

        failure = listener.doRead()

        # No failure is returned; see the comment in PostgresListener.doRead()
        # that explains why we don't do that.
        self.assertThat(failure, Is(None))

        # The listener has begun disconnecting.
        self.assertThat(listener.disconnecting, IsInstance(Deferred))
        # Wait for disconnection to complete.
        yield listener.disconnecting
        # The listener has removed itself from the reactor.
        self.assertThat(reactor.removeReader, MockCalledOnceWith(listener))
        # connectionLost() has been called with a simple ConnectionLost.
        self.assertThat(listener.connectionLost, MockCalledOnceWith(ANY))
        [failure] = listener.connectionLost.call_args[0]
        self.assertThat(failure, IsInstance(Failure))
        self.assertThat(failure.value, IsInstance(error.ConnectionLost))

    def test__doRead_adds_notifies_to_notifications(self):
        listener = PostgresListener()
        notifications = [
            FakeNotify(
                channel=factory.make_name("channel_action"),
                payload=factory.make_name("payload"))
            for _ in range(3)
            ]

        connection = self.patch(listener, "connection")
        connection.connection.poll.return_value = None
        # Add the notifications twice, so it can test that duplicates are
        # accumulated together.
        connection.connection.notifies = notifications + notifications
        self.patch(listener, "handleNotify")

        listener.doRead()
        self.assertItemsEqual(
            listener.notifications, set(notifications))

    @wait_for_reactor
    @inlineCallbacks
    def test__listener_ignores_ENOENT_when_removing_itself_from_reactor(self):
        listener = PostgresListener()

        self.patch(reactor, "addReader")
        self.patch(reactor, "removeReader")

        # removeReader() is going to have a nasty accident.
        enoent = IOError("ENOENT")
        enoent.errno = errno.ENOENT
        reactor.removeReader.side_effect = enoent

        # The listener starts and stops without issue.
        yield listener.start()
        yield listener.stop()

        # addReader() and removeReader() were both called.
        self.assertThat(reactor.addReader, MockCalledOnceWith(listener))
        self.assertThat(reactor.removeReader, MockCalledOnceWith(listener))

    @wait_for_reactor
    @inlineCallbacks
    def test__listener_waits_for_notifier_to_complete(self):
        listener = PostgresListener()

        yield listener.start()
        try:
            self.assertTrue(listener.notifier.running)
        finally:
            yield listener.stop()
            self.assertFalse(listener.notifier.running)


class TransactionalHelpersMixin:
    """Helpers performing actions in transactions."""

    def make_listener_without_delay(self):
        listener = PostgresListener()
        self.patch(listener, "HANDLE_NOTIFY_DELAY", 0)
        return listener

    @transactional
    def get_node(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node

    @transactional
    def create_node(self, params=None):
        if params is None:
            params = {}
        params['with_boot_disk'] = False
        return factory.make_Node(**params)

    @transactional
    def update_node(self, system_id, params):
        node = Node.objects.get(system_id=system_id)
        for key, value in params.items():
            setattr(node, key, value)
        return node.save()

    @transactional
    def delete_node(self, system_id):
        node = Node.objects.get(system_id=system_id)
        node.delete()

    @transactional
    def create_device_with_parent(self, params=None):
        if params is None:
            params = {}
        parent = factory.make_Node(with_boot_disk=False)
        params["installable"] = False
        params["parent"] = parent
        device = factory.make_Node(**params)
        return device, parent

    @transactional
    def get_node_boot_interface(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node.get_boot_interface()

    @transactional
    def create_nodegroup(self, params=None):
        if params is None:
            params = {}
        return factory.make_NodeGroup(**params)

    @transactional
    def update_nodegroup(self, id, params):
        nodegroup = NodeGroup.objects.get(id=id)
        for key, value in params.items():
            setattr(nodegroup, key, value)
        return nodegroup.save()

    @transactional
    def delete_nodegroup(self, id):
        nodegroup = NodeGroup.objects.get(id=id)
        nodegroup.delete()

    @transactional
    def create_nodegroupinterface(self, nodegroup, params=None):
        if params is None:
            params = {}
        return factory.make_NodeGroupInterface(nodegroup, **params)

    @transactional
    def update_nodegroupinterface(self, id, params):
        interface = NodeGroupInterface.objects.get(id=id)
        for key, value in params.items():
            setattr(interface, key, value)
        return interface.save()

    @transactional
    def update_nodegroupinterface_subnet_mask(self, id, subnet_mask):
        interface = NodeGroupInterface.objects.get(id=id)
        # This is now a special case, since the subnet_mask no longer
        # belongs to the NodeGroupInterface. We'll need to explicitly
        # save *only* the Subnet, without saving the NodeGroupInterface.
        # Otherwise, Django will ignorantly update the table, and our
        # test case may pass with a false-positive.
        interface.subnet_mask = subnet_mask
        interface.subnet.save()

    @transactional
    def delete_nodegroupinterface(self, id):
        interface = NodeGroupInterface.objects.get(id=id)
        interface.delete()

    @transactional
    def create_fabric(self, params=None):
        if params is None:
            params = {}
        return factory.make_Fabric(**params)

    @transactional
    def update_fabric(self, id, params):
        fabric = Fabric.objects.get(id=id)
        for key, value in params.items():
            setattr(fabric, key, value)
        return fabric.save()

    @transactional
    def delete_fabric(self, id):
        fabric = Fabric.objects.get(id=id)
        fabric.delete()

    @transactional
    def create_space(self, params=None):
        if params is None:
            params = {}
        return factory.make_Space(**params)

    @transactional
    def update_space(self, id, params):
        space = Space.objects.get(id=id)
        for key, value in params.items():
            setattr(space, key, value)
        return space.save()

    @transactional
    def delete_space(self, id):
        space = Space.objects.get(id=id)
        space.delete()

    @transactional
    def create_subnet(self, params=None):
        if params is None:
            params = {}
        return factory.make_Subnet(**params)

    @transactional
    def update_subnet(self, id, params):
        subnet = Subnet.objects.get(id=id)
        for key, value in params.items():
            setattr(subnet, key, value)
        return subnet.save()

    @transactional
    def delete_subnet(self, id):
        subnet = Subnet.objects.get(id=id)
        subnet.delete()

    @transactional
    def create_vlan(self, params=None):
        if params is None:
            params = {}
        return factory.make_VLAN(**params)

    @transactional
    def update_vlan(self, id, params):
        vlan = VLAN.objects.get(id=id)
        for key, value in params.items():
            setattr(vlan, key, value)
        return vlan.save()

    @transactional
    def delete_vlan(self, id):
        vlan = VLAN.objects.get(id=id)
        vlan.delete()

    @transactional
    def create_zone(self, params=None):
        if params is None:
            params = {}
        return factory.make_Zone(**params)

    @transactional
    def update_zone(self, id, params):
        zone = Zone.objects.get(id=id)
        for key, value in params.items():
            setattr(zone, key, value)
        return zone.save()

    @transactional
    def delete_zone(self, id):
        zone = Zone.objects.get(id=id)
        zone.delete()

    @transactional
    def create_tag(self, params=None):
        if params is None:
            params = {}
        return factory.make_Tag(**params)

    @transactional
    def add_node_to_tag(self, node, tag):
        node.tags.add(tag)
        node.save()

    @transactional
    def remove_node_from_tag(self, node, tag):
        node.tags.remove(tag)
        node.save()

    @transactional
    def update_tag(self, id, params):
        tag = Tag.objects.get(id=id)
        for key, value in params.items():
            setattr(tag, key, value)
        return tag.save()

    @transactional
    def delete_tag(self, id):
        tag = Tag.objects.get(id=id)
        tag.delete()

    @transactional
    def create_user(self, params=None):
        if params is None:
            params = {}
        return factory.make_User(**params)

    @transactional
    def update_user(self, id, params):
        user = User.objects.get(id=id)
        for key, value in params.items():
            setattr(user, key, value)
        return user.save()

    @transactional
    def delete_user(self, id):
        user = User.objects.get(id=id)
        user.consumers.all().delete()
        user.delete()

    @transactional
    def create_event(self, params=None):
        if params is None:
            params = {}
        return factory.make_Event(**params)

    @transactional
    def update_event(self, id, params):
        event = Event.objects.get(id=id)
        for key, value in params.items():
            setattr(event, key, value)
        return event.save()

    @transactional
    def delete_event(self, id):
        event = Event.objects.get(id=id)
        event.delete()

    @transactional
    def create_staticipaddress(self, params=None):
        if params is None:
            params = {}
        return factory.make_StaticIPAddress(**params)

    @transactional
    def update_staticipaddress(self, id, params):
        ip = StaticIPAddress.objects.get(id=id)
        for key, value in params.items():
            setattr(ip, key, value)
        return ip.save()

    @transactional
    def delete_staticipaddress(self, id):
        sip = StaticIPAddress.objects.get(id=id)
        sip.delete()

    @transactional
    def get_ipaddress_subnet(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet

    @transactional
    def get_ipaddress_vlan(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet.vlan

    @transactional
    def get_ipaddress_fabric(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet.vlan.fabric

    @transactional
    def get_ipaddress_space(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet.space

    @transactional
    def create_noderesult(self, params=None):
        if params is None:
            params = {}
        return factory.make_NodeResult_for_commissioning(**params)

    @transactional
    def delete_noderesult(self, id):
        result = NodeResult.objects.get(id=id)
        result.delete()

    @transactional
    def create_interface(self, params=None):
        if params is None:
            params = {}
        return factory.make_Interface(INTERFACE_TYPE.PHYSICAL, **params)

    @transactional
    def delete_interface(self, id):
        interface = Interface.objects.get(id=id)
        interface.delete()

    @transactional
    def update_interface(self, id, params):
        interface = Interface.objects.get(id=id)
        for key, value in params.items():
            setattr(interface, key, value)
        return interface.save()

    @transactional
    def get_interface_vlan(self, id):
        interface = Interface.objects.get(id=id)
        return interface.vlan

    @transactional
    def get_interface_fabric(self, id):
        interface = Interface.objects.get(id=id)
        return interface.vlan.fabric

    @transactional
    def create_blockdevice(self, params=None):
        if params is None:
            params = {}
        return factory.make_BlockDevice(**params)

    @transactional
    def create_physicalblockdevice(self, params=None):
        if params is None:
            params = {}
        return factory.make_PhysicalBlockDevice(**params)

    @transactional
    def create_virtualblockdevice(self, params=None):
        if params is None:
            params = {}
        return factory.make_VirtualBlockDevice(**params)

    @transactional
    def delete_blockdevice(self, id):
        blockdevice = BlockDevice.objects.get(id=id)
        blockdevice.delete()

    @transactional
    def update_blockdevice(self, id, params):
        blockdevice = BlockDevice.objects.get(id=id)
        for key, value in params.items():
            setattr(blockdevice, key, value)
        return blockdevice.save()

    @transactional
    def update_physicalblockdevice(self, id, params):
        blockdevice = PhysicalBlockDevice.objects.get(id=id)
        for key, value in params.items():
            setattr(blockdevice, key, value)
        return blockdevice.save()

    @transactional
    def update_virtualblockdevice(self, id, params):
        blockdevice = VirtualBlockDevice.objects.get(id=id)
        for key, value in params.items():
            setattr(blockdevice, key, value)
        return blockdevice.save()

    @transactional
    def create_partitiontable(self, params=None):
        if params is None:
            params = {}
        return factory.make_PartitionTable(**params)

    @transactional
    def delete_partitiontable(self, id):
        partitiontable = PartitionTable.objects.get(id=id)
        partitiontable.delete()

    @transactional
    def update_partitiontable(self, id, params):
        partitiontable = PartitionTable.objects.get(id=id)
        for key, value in params.items():
            setattr(partitiontable, key, value)
        return partitiontable.save()

    @transactional
    def create_partition(self, params=None):
        if params is None:
            params = {}
        return factory.make_Partition(**params)

    @transactional
    def delete_partition(self, id):
        partition = Partition.objects.get(id=id)
        partition.delete()

    @transactional
    def update_partition(self, id, params):
        partition = Partition.objects.get(id=id)
        for key, value in params.items():
            setattr(partition, key, value)
        return partition.save()

    @transactional
    def create_filesystem(self, params=None):
        if params is None:
            params = {}
        return factory.make_Filesystem(**params)

    @transactional
    def delete_filesystem(self, id):
        filesystem = Filesystem.objects.get(id=id)
        filesystem.delete()

    @transactional
    def update_filesystem(self, id, params):
        filesystem = Filesystem.objects.get(id=id)
        for key, value in params.items():
            setattr(filesystem, key, value)
        return filesystem.save()

    @transactional
    def create_filesystemgroup(self, params=None):
        if params is None:
            params = {}
        return factory.make_FilesystemGroup(**params)

    @transactional
    def delete_filesystemgroup(self, id):
        filesystemgroup = FilesystemGroup.objects.get(id=id)
        filesystemgroup.delete()

    @transactional
    def update_filesystemgroup(self, id, params):
        filesystemgroup = FilesystemGroup.objects.get(id=id)
        for key, value in params.items():
            setattr(filesystemgroup, key, value)
        return filesystemgroup.save()

    @transactional
    def create_cacheset(self, params=None):
        if params is None:
            params = {}
        return factory.make_CacheSet(**params)

    @transactional
    def delete_cacheset(self, id):
        cacheset = CacheSet.objects.get(id=id)
        cacheset.delete()

    @transactional
    def update_cacheset(self, id, params):
        cacheset = CacheSet.objects.get(id=id)
        for key, value in params.items():
            setattr(cacheset, key, value)
        return cacheset.save()

    @transactional
    def create_sshkey(self, params=None):
        if params is None:
            params = {}
        return factory.make_SSHKey(**params)

    @transactional
    def delete_sshkey(self, id):
        key = SSHKey.objects.get(id=id)
        key.delete()

    @transactional
    def create_sslkey(self, params=None):
        if params is None:
            params = {}
        return factory.make_SSLKey(**params)

    @transactional
    def delete_sslkey(self, id):
        key = SSLKey.objects.get(id=id)
        key.delete()


class TestNodeListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers code."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
        ('device', {
            'params': {'installable': False},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            node = yield deferToDatabase(self.create_node, self.params)
            yield dv.get(timeout=2)
            self.assertEqual(('create', node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        node = yield deferToDatabase(self.create_node, self.params)
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_node,
                node.system_id,
                {'hostname': factory.make_name('hostname')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        node = yield deferToDatabase(self.create_node, self.params)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_node, node.system_id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestDeviceWithParentListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        parent = yield deferToDatabase(self.create_node)
        yield listener.start()
        try:
            yield deferToDatabase(
                self.create_node, {
                    "installable": False,
                    "parent": parent,
                    })
            yield dv.get(timeout=2)
            self.assertEqual(('update', parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_node,
                device.system_id,
                {'hostname': factory.make_name('hostname')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_node, device.system_id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', parent.system_id), dv.value)
        finally:
            yield listener.stop()


class TestClusterListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodegroup", lambda *args: dv.set(args))
        yield listener.start()
        try:
            nodegroup = yield deferToDatabase(self.create_nodegroup)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % nodegroup.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodegroup", lambda *args: dv.set(args))
        nodegroup = yield deferToDatabase(self.create_nodegroup)

        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_nodegroup,
                nodegroup.id,
                {'cluster_name': factory.make_name('cluster_name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % nodegroup.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodegroup", lambda *args: dv.set(args))
        nodegroup = yield deferToDatabase(self.create_nodegroup)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_nodegroup, nodegroup.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % nodegroup.id), dv.value)
        finally:
            yield listener.stop()


class TestClusterInterfaceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster interface
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_nodegroup_update_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        nodegroup = yield deferToDatabase(self.create_nodegroup)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodegroup", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.create_nodegroupinterface, nodegroup)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % nodegroup.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_nodegroup_update_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        nodegroup = yield deferToDatabase(self.create_nodegroup)
        interface = yield deferToDatabase(
            self.create_nodegroupinterface, nodegroup)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodegroup", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_nodegroupinterface,
                interface.id,
                {'name': factory.make_name('name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % nodegroup.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_nodegroup_update_handler_on_update_subnet_mask(self):
        yield deferToDatabase(register_all_triggers)
        nodegroup = yield deferToDatabase(self.create_nodegroup)
        interface = yield deferToDatabase(
            self.create_nodegroupinterface, nodegroup,
            params=dict(ip='10.0.0.1', subnet_mask='255.255.255.0'))

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodegroup", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_nodegroupinterface_subnet_mask,
                interface.id, '255.255.0.0')
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % nodegroup.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_nodegroup_update_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        nodegroup = yield deferToDatabase(self.create_nodegroup)
        interface = yield deferToDatabase(
            self.create_nodegroupinterface, nodegroup)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("nodegroup", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_nodegroupinterface, interface.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % nodegroup.id), dv.value)
        finally:
            yield listener.stop()


class TestZoneListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the zone
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("zone", lambda *args: dv.set(args))
        yield listener.start()
        try:
            zone = yield deferToDatabase(self.create_zone)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % zone.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("zone", lambda *args: dv.set(args))
        zone = yield deferToDatabase(self.create_zone)

        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_zone,
                zone.id,
                {'cluster_name': factory.make_name('cluster_name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % zone.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("zone", lambda *args: dv.set(args))
        zone = yield deferToDatabase(self.create_zone)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_zone, zone.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % zone.id), dv.value)
        finally:
            yield listener.stop()


class TestTagListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the tag
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("tag", lambda *args: dv.set(args))
        yield listener.start()
        try:
            tag = yield deferToDatabase(self.create_tag)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % tag.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("tag", lambda *args: dv.set(args))
        tag = yield deferToDatabase(self.create_tag)

        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_tag,
                tag.id,
                {'name': factory.make_name('tag')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % tag.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("tag", lambda *args: dv.set(args))
        tag = yield deferToDatabase(self.create_tag)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_tag, tag.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % tag.id), dv.value)
        finally:
            yield listener.stop()


class TestNodeTagListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_node_tags table."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
        ('device', {
            'params': {'installable': False},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.add_node_to_tag, node, tag)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.remove_node_from_tag, node, tag)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_node_handler_with_update_on_tag_rename(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        tag = yield deferToDatabase(self.create_tag)
        yield deferToDatabase(self.add_node_to_tag, node, tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            tag = yield deferToDatabase(
                self.update_tag, tag.id, {'name': factory.make_name("tag")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestDeviceWithParentTagListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_node_tags table."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.add_node_to_tag, device, tag)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        tag = yield deferToDatabase(self.create_tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.remove_node_from_tag, device, tag)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_node_handler_with_update_on_tag_rename(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        tag = yield deferToDatabase(self.create_tag)
        yield deferToDatabase(self.add_node_to_tag, device, tag)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            tag = yield deferToDatabase(
                self.update_tag, tag.id, {'name': factory.make_name("tag")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()


class TestUserListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the user
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.start()
        try:
            user = yield deferToDatabase(self.create_user)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % user.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        user = yield deferToDatabase(self.create_user)

        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_user,
                user.id,
                {'username': factory.make_name('username')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        user = yield deferToDatabase(self.create_user)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_user, user.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % user.id), dv.value)
        finally:
            yield listener.stop()


class TestEventListener(DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the event
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("event", lambda *args: dv.set(args))
        yield listener.start()
        try:
            event = yield deferToDatabase(self.create_event)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % event.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("event", lambda *args: dv.set(args))
        event = yield deferToDatabase(self.create_event)

        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_event,
                event.id,
                {'description': factory.make_name('description')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % event.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("event", lambda *args: dv.set(args))
        event = yield deferToDatabase(self.create_event)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_event, event.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % event.id), dv.value)
        finally:
            yield listener.stop()


class TestNodeEventListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_event table that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
        ('device', {
            'params': {'installable': False},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_event, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestDeviceWithParentEventListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_event table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_event, {"node": device})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()


class TestNodeStaticIPAddressListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interfacestaticipaddresslink table that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True, 'interface': True},
            'listener': 'node',
            }),
        ('device', {
            'params': {'installable': False, 'interface': True},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.create_staticipaddress, {"interface": interface})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        sip = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_staticipaddress, sip.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestDeviceWithParentStaticIPAddressListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interfacestaticipaddresslink table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.create_staticipaddress, {"interface": interface})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        sip = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_staticipaddress, sip.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()


class TestNodeNodeResultListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    metadataserver_noderesult table that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
        ('device', {
            'params': {'installable': False},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_noderesult, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        result = yield deferToDatabase(self.create_noderesult, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_noderesult, result.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestDeviceWithParentNodeResultListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    metadataserver_noderesult table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_noderesult, {"node": device})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        result = yield deferToDatabase(
            self.create_noderesult, {"node": device})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_noderesult, result.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()


class TestNodeInterfaceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interface table that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
        ('device', {
            'params': {'installable': False},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_interface, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_interface, interface.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "mac_address": factory.make_MAC()
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_old_node_on_update(self):
        yield deferToDatabase(register_all_triggers)
        node1 = yield deferToDatabase(self.create_node, self.params)
        node2 = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node1})
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = PostgresListener()
        listener.register(self.listener, set_defer_value)
        yield listener.start()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "node": node2
                })
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertItemsEqual([
                ('update', '%s' % node1.system_id),
                ('update', '%s' % node2.system_id),
                ], [dvs[0].value, dvs[1].value])
        finally:
            yield listener.stop()


class TestDeviceWithParentInterfaceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_interface table that notifies its node."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_interface, {"node": device})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        interface = yield deferToDatabase(
            self.create_interface, {"node": device})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_interface, interface.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(self.create_device_with_parent)
        interface = yield deferToDatabase(
            self.create_interface, {"node": device})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "mac_address": factory.make_MAC()
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_old_node_on_update(self):
        yield deferToDatabase(register_all_triggers)
        device1, parent1 = yield deferToDatabase(
            self.create_device_with_parent)
        device2, parent2 = yield deferToDatabase(
            self.create_device_with_parent)
        interface = yield deferToDatabase(
            self.create_interface, {"node": device1})
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = PostgresListener()
        listener.register("node", set_defer_value)
        yield listener.start()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "node": device2
                })
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertItemsEqual([
                ('update', '%s' % parent1.system_id),
                ('update', '%s' % parent2.system_id),
                ], [dvs[0].value, dvs[1].value])
        finally:
            yield listener.stop()


class TestFabricListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("fabric", lambda *args: dv.set(args))
        yield listener.start()
        try:
            fabric = yield deferToDatabase(self.create_fabric)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % fabric.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("fabric", lambda *args: dv.set(args))
        fabric = yield deferToDatabase(self.create_fabric)

        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_fabric,
                fabric.id,
                {'name': factory.make_name('name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % fabric.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("fabric", lambda *args: dv.set(args))
        fabric = yield deferToDatabase(self.create_fabric)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_fabric, fabric.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % fabric.id), dv.value)
        finally:
            yield listener.stop()


class TestVLANListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        fabric = yield deferToDatabase(self.create_fabric)
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vlan", lambda *args: dv.set(args))
        yield listener.start()
        try:
            vlan = yield deferToDatabase(self.create_vlan, {'fabric': fabric})
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % vlan.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        fabric = yield deferToDatabase(self.create_fabric)
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vlan", lambda *args: dv.set(args))
        vlan = yield deferToDatabase(self.create_vlan, {'fabric': fabric})

        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_vlan,
                vlan.id,
                {'name': factory.make_name('name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % vlan.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        fabric = yield deferToDatabase(self.create_fabric)
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("vlan", lambda *args: dv.set(args))
        vlan = yield deferToDatabase(self.create_vlan, {'fabric': fabric})
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_vlan, vlan.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % vlan.id), dv.value)
        finally:
            yield listener.stop()


class TestSubnetListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.start()
        try:
            subnet = yield deferToDatabase(self.create_subnet)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % subnet.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        subnet = yield deferToDatabase(self.create_subnet)

        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {'name': factory.make_name('name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % subnet.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        subnet = yield deferToDatabase(self.create_subnet)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % subnet.id), dv.value)
        finally:
            yield listener.stop()


class TestSpaceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the cluster
    triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_create_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("space", lambda *args: dv.set(args))
        yield listener.start()
        try:
            space = yield deferToDatabase(self.create_space)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '%s' % space.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_update_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("space", lambda *args: dv.set(args))
        space = yield deferToDatabase(self.create_space)

        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_space,
                space.id,
                {'name': factory.make_name('name')})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % space.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_delete_notification(self):
        yield deferToDatabase(register_all_triggers)
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("space", lambda *args: dv.set(args))
        space = yield deferToDatabase(self.create_space)
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_space, space.id)
            yield dv.get(timeout=2)
            self.assertEqual(('delete', '%s' % space.id), dv.value)
        finally:
            yield listener.stop()


class TestNodeNetworkListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_fabric, maasserver_space, maasserver_subnet, and
    maasserver_vlan tables that notifies affected nodes."""

    scenarios = (
        ('node', {
            'params': {'installable': True, 'interface': True},
            'listener': 'node',
            }),
        ('device', {
            'params': {'installable': False, 'interface': True},
            'listener': 'device',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_iface_with_update_on_fabric_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        fabric = yield deferToDatabase(self.get_interface_fabric, interface.id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_fabric,
                fabric.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_iface_with_update_on_vlan_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        vlan = yield deferToDatabase(self.get_interface_vlan, interface.id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_vlan,
                vlan.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_subnet_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        subnet = yield deferToDatabase(self.get_ipaddress_subnet, ipaddress.id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_space_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        space = yield deferToDatabase(self.get_ipaddress_space, ipaddress.id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_space, space.id,
                {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_ip_address_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        interface = yield deferToDatabase(
            self.get_node_boot_interface, node.system_id)
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "subnet": subnet,
                "ip": "",
                })

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, ipaddress.id,
                {"ip": selected_ip})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestDeviceWithParentNetworkListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_fabric, maasserver_space, maasserver_subnet, and
    maasserver_vlan tables that notifies affected nodes."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_iface_with_update_on_fabric_update(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        fabric = yield deferToDatabase(self.get_interface_fabric, interface.id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_fabric,
                fabric.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_iface_with_update_on_vlan_update(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        vlan = yield deferToDatabase(self.get_interface_vlan, interface.id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_vlan,
                vlan.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_subnet_update(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        subnet = yield deferToDatabase(self.get_ipaddress_subnet, ipaddress.id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id, {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_space_update(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {"interface": interface})
        space = yield deferToDatabase(self.get_ipaddress_space, ipaddress.id)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_space, space.id,
                {"name": factory.make_name("name")})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_ip_address_update(self):
        yield deferToDatabase(register_all_triggers)
        device, parent = yield deferToDatabase(
            self.create_device_with_parent, {"interface": True})
        interface = yield deferToDatabase(
            self.get_node_boot_interface, device.system_id)
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "subnet": subnet,
                "ip": "",
                })

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, ipaddress.id,
                {"ip": selected_ip})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % parent.system_id), dv.value)
        finally:
            yield listener.stop()


class TestStaticIPAddressSubnetListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_staticipaddress tables that notifies affected subnets."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_update_on_subnet(self):
        yield deferToDatabase(register_all_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "subnet": subnet,
                "ip": "",
                })

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("subnet", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_staticipaddress,
                ipaddress.id, {"ip": selected_ip})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % subnet.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_update_on_old_and_new_subnet(self):
        yield deferToDatabase(register_all_triggers)
        old_subnet = yield deferToDatabase(self.create_subnet)
        new_subnet = yield deferToDatabase(self.create_subnet)
        selected_ip = factory.pick_ip_in_network(new_subnet.get_ipnetwork())
        ipaddress = yield deferToDatabase(
            self.create_staticipaddress, {
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "subnet": old_subnet,
                "ip": "",
                })
        dvs = [DeferredValue(), DeferredValue()]

        def set_defer_value(*args):
            for dv in dvs:
                if not dv.isSet:
                    dv.set(args)
                    break

        listener = PostgresListener()
        listener.register("subnet", set_defer_value)
        yield listener.start()
        try:
            yield deferToDatabase(self.update_staticipaddress, ipaddress.id, {
                "ip": selected_ip,
                "subnet": new_subnet,
                })
            yield dvs[0].get(timeout=2)
            yield dvs[1].get(timeout=2)
            self.assertItemsEqual([
                ('update', '%s' % old_subnet.id),
                ('update', '%s' % new_subnet.id),
                ], [dvs[0].value, dvs[1].value])
        finally:
            yield listener.stop()


class TestNodeBlockDeviceListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_blockdevice, maasserver_physicalblockdevice, and
    maasserver_virtualblockdevice tables that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_blockdevice, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_blockdevice, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_blockdevice, blockdevice.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_blockdevice, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.update_blockdevice, blockdevice.id, {
                "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_physicalblockdevice_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_physicalblockdevice, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_physicalblockdevice, blockdevice.id, {
                    "model": factory.make_name("model")
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_virtualblockdevice_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        blockdevice = yield deferToDatabase(
            self.create_virtualblockdevice, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_virtualblockdevice, blockdevice.id, {
                    "uuid": factory.make_UUID()
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestNodePartitionTableListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_partitiontable tables that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_partitiontable, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partitiontable = yield deferToDatabase(
            self.create_partitiontable, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.delete_partitiontable, partitiontable.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partitiontable = yield deferToDatabase(
            self.create_partitiontable, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_partitiontable, partitiontable.id, {
                    "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestNodePartitionListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_partition tables that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_partition, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_partition, partition.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            # Only downsize the partition otherwise the test may fail due
            # to the random number being generated is greater than the mock
            # available disk space
            yield deferToDatabase(self.update_partition, partition.id, {
                "size": partition.size - 1,
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestNodeFilesystemListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_filesystem tables that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.create_filesystem, {"partition": partition})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})
        filesystem = yield deferToDatabase(
            self.create_filesystem, {"partition": partition})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_filesystem, filesystem.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})
        filesystem = yield deferToDatabase(
            self.create_filesystem, {"partition": partition})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.update_filesystem, filesystem.id, {
                "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestNodeFilesystemgroupListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_filesystemgroup tables that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True, 'with_boot_disk': True},
            'listener': 'node',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(self.create_partitiontable, {'node': node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_filesystemgroup, {"node": node})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(self.create_partitiontable, {'node': node})
        filesystemgroup = yield deferToDatabase(
            self.create_filesystemgroup, {
                "node": node, "group_type": "raid-5"})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.delete_filesystemgroup, filesystemgroup.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        yield deferToDatabase(self.create_partitiontable, {'node': node})
        filesystemgroup = yield deferToDatabase(
            self.create_filesystemgroup, {
                "node": node, "group_type": "raid-5"})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.update_filesystemgroup, filesystemgroup.id, {
                    "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestNodeCachesetListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the triggers on
    maasserver_cacheset tables that notifies its node."""

    scenarios = (
        ('node', {
            'params': {'installable': True},
            'listener': 'node',
            }),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(
                self.create_cacheset, {"node": node, "partition": partition})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})
        cacheset = yield deferToDatabase(
            self.create_cacheset, {"node": node, "partition": partition})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_cacheset, cacheset.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_update(self):
        yield deferToDatabase(register_all_triggers)
        node = yield deferToDatabase(self.create_node, self.params)
        partition = yield deferToDatabase(
            self.create_partition, {"node": node})
        cacheset = yield deferToDatabase(
            self.create_cacheset, {"node": node, "partition": partition})

        listener = PostgresListener()
        dv = DeferredValue()
        listener.register(self.listener, lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.update_cacheset, cacheset.id, {
                "size": random.randint(3000 * 1000, 1000 * 1000 * 1000)
                })
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % node.system_id), dv.value)
        finally:
            yield listener.stop()


class TestUserSSHKeyListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the maasserver_sshkey
    table that notifies its user."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_sshkey, {"user": user})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        user = yield deferToDatabase(self.create_user)
        sshkey = yield deferToDatabase(self.create_sshkey, {"user": user})

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_sshkey, sshkey.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stop()


class TestUserSSLKeyListener(
        DjangoTransactionTestCase, TransactionalHelpersMixin):
    """End-to-end test of both the listeners code and the maasserver_sslkey
    table that notifies its user."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_create(self):
        yield deferToDatabase(register_all_triggers)
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.create_sslkey, {"user": user})
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_with_update_on_delete(self):
        yield deferToDatabase(register_all_triggers)
        user = yield deferToDatabase(self.create_user)
        sslkey = yield deferToDatabase(self.create_sslkey, {"user": user})

        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("user", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToDatabase(self.delete_sslkey, sslkey.id)
            yield dv.get(timeout=2)
            self.assertEqual(('update', '%s' % user.id), dv.value)
        finally:
            yield listener.stop()
