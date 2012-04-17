# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver messages."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import json
import socket

from maasserver.exceptions import NoRabbit
from maasserver.messages import (
    MAASMessenger,
    MESSENGER_EVENT,
    MessengerBase,
    )
from maasserver.models import Node
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestModelTestCase
from maasserver.tests.models import MessagesTestModel


class FakeProducer:
    """A fake RabbitProducer that simply records published messages."""

    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class TestMessenger(MessengerBase):

    def create_msg(self, event_name, instance):
        return [event_name, instance]


class MessengerBaseTest(TestModelTestCase):

    app = 'maasserver.tests'

    def test_update_obj_publishes_message_if_created(self):
        producer = FakeProducer()
        messenger = TestMessenger(MessagesTestModel, producer)
        instance = factory.getRandomString()
        messenger.update_obj(MessagesTestModel, instance, True)
        self.assertEqual(
            [[MESSENGER_EVENT.CREATED, instance]], producer.messages)

    def test_update_obj_publishes_message_if_not_created(self):
        producer = FakeProducer()
        messenger = TestMessenger(MessagesTestModel, producer)
        instance = factory.getRandomString()
        messenger.update_obj(MessagesTestModel, instance, False)
        self.assertEqual(
            [[MESSENGER_EVENT.UPDATED, instance]], producer.messages)

    def test_delete_obj_publishes_message(self):
        producer = FakeProducer()
        messenger = TestMessenger(MessagesTestModel, producer)
        instance = factory.getRandomString()
        messenger.delete_obj(MessagesTestModel, instance)
        self.assertEqual(
            [[MESSENGER_EVENT.DELETED, instance]], producer.messages)

    def test_register_registers_update_signal(self):
        producer = FakeProducer()
        messenger = TestMessenger(MessagesTestModel, producer)
        obj = MessagesTestModel(name=factory.getRandomString())
        obj.save()
        messenger.register()
        obj.save()
        self.assertEqual(
            [[MESSENGER_EVENT.UPDATED, obj]], producer.messages)

    def test_register_registers_created_signal(self):
        producer = FakeProducer()
        messenger = TestMessenger(MessagesTestModel, producer)
        messenger.register()
        obj = MessagesTestModel(name=factory.getRandomString())
        obj.save()
        self.assertEqual(
            [[MESSENGER_EVENT.CREATED, obj]], producer.messages)

    def test_register_registers_delete_signal(self):
        obj = MessagesTestModel(name=factory.getRandomString())
        obj.save()
        producer = FakeProducer()
        messenger = TestMessenger(MessagesTestModel, producer)
        messenger.register()
        obj.delete()
        self.assertEqual(
            [[MESSENGER_EVENT.DELETED, obj]], producer.messages)

    def test_publish_message_publishes_message(self):
        event = factory.getRandomString()
        instance = {factory.getRandomString(): factory.getRandomString()}
        messenger = TestMessenger(MessagesTestModel, FakeProducer())
        messenger.publish_message(messenger.create_msg(event, instance))
        self.assertEqual([[event, instance]], messenger.producer.messages)

    def test_publish_message_swallows_missing_rabbit(self):
        event = factory.getRandomString()
        instance = {factory.getRandomString(): factory.getRandomString()}

        def fail_for_lack_of_rabbit(*args, **kwargs):
            raise NoRabbit("I'm pretending not to have a RabbitMQ.")

        messenger = TestMessenger(MessagesTestModel, FakeProducer())
        messenger.producer.publish = fail_for_lack_of_rabbit

        messenger.publish_message(messenger.create_msg(event, instance))
        self.assertEqual([], messenger.producer.messages)

    def test_publish_message_propagates_exceptions(self):
        event = factory.getRandomString()
        instance = {factory.getRandomString(): factory.getRandomString()}

        def fail_despite_having_a_rabbit(*args, **kwargs):
            raise socket.error("I have a rabbit but I fail anyway.")

        messenger = TestMessenger(MessagesTestModel, FakeProducer())
        messenger.producer.publish = fail_despite_having_a_rabbit

        self.assertRaises(
            socket.error,
            messenger.publish_message, messenger.create_msg(event, instance))
        self.assertEqual([], messenger.producer.messages)


class MAASMessengerTest(TestModelTestCase):

    app = 'maasserver.tests'

    def test_event_key(self):
        producer = FakeProducer()
        event_name = factory.getRandomString()
        obj = MessagesTestModel(name=factory.getRandomString())
        messenger = MAASMessenger(MessagesTestModel, producer)
        self.assertEqual(
            '%s.%s' % ('MessagesTestModel', event_name),
            messenger.event_key(event_name, obj))

    def test_create_msg(self):
        producer = FakeProducer()
        messenger = MAASMessenger(Node, producer)
        event_name = factory.getRandomString()
        obj_name = factory.getRandomString()
        obj = MessagesTestModel(name=obj_name)
        obj.save()
        msg = messenger.create_msg(event_name, obj)
        decoded_msg = json.loads(msg)
        self.assertItemsEqual(['instance', 'event_key'], list(decoded_msg))
        self.assertItemsEqual(
            ['id', 'name'], list(decoded_msg['instance']))
        self.assertEqual(
            obj_name, decoded_msg['instance']['name'])
