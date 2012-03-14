# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Messages."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "MaaSMessenger",
    "MessengerBase",
    "messaging",
    ]


from abc import (
    ABCMeta,
    abstractmethod,
    )

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.signals import (
    post_delete,
    post_save,
    )
from maasserver.models import Node
from maasserver.rabbit import RabbitMessaging

# This is the name of the exchange where changes to MaaS's model objects will
# be published.
MODEL_EXCHANGE_NAME = "MaaS Model Exchange"


class MESSENGER_EVENT:
    CREATED = 'created'
    UPDATED = 'updated'
    DELETED = 'deleted'


class MessengerBase:
    """Generic class that will publish events to a producer when a model
    object is changed.
    """

    __metaclass__ = ABCMeta

    def __init__(self, model_class, producer):
        """
        :param model_class: The model class to track.
        :type model_class: django.db.models.Model
        :param producer: The producer used to publish events.
        :type producer: maasserer.rabbit.db.models.RabbitExchange
        """
        self.model_class = model_class
        self.producer = producer

    @abstractmethod
    def create_msg(self, event_name, instance):
        """Format a message from the given event_name and instance."""

    def update_obj(self, sender, instance, created, **kwargs):
        event_name = (
            MESSENGER_EVENT.CREATED if created
            else MESSENGER_EVENT.UPDATED)
        message = self.create_msg(event_name, instance)
        self.producer.publish(message)

    def delete_obj(self, sender, instance, **kwargs):
        message = self.create_msg(MESSENGER_EVENT.DELETED, instance)
        self.producer.publish(message)

    def register(self):
        post_save.connect(
            receiver=self.update_obj, weak=False, sender=self.model_class)
        post_delete.connect(
            receiver=self.delete_obj, weak=False, sender=self.model_class)


class MaaSMessenger(MessengerBase):
    """A messenger tailored to suit MaaS' UI (JavaScript) requirements.

    The format of the event's payload will be::

        {
            "event_key": "$ModelClass.$MESSENGER_EVENT",
            "instance": jsonified instance
        }

    For instance, when a Node is created, the event's payload will look like
    this::

        {
            "event_key": "Node.created",
            "instance": {
                "hostname": "sun",
                "system_id": "node-17ca41c2-6c39-11e1-a961-00219bd0a2de",
                "architecture": "i386",
                [...]
            }
        }
    """

    def create_msg(self, event_name, instance):
        event_key = self.event_key(event_name, instance)
        message = DjangoJSONEncoder().encode({
            'instance':
                {k: v for k, v in instance.__dict__.items()
                 if not k.startswith('_')},
            'event_key': event_key,

        })
        return message

    def event_key(self, event_name, instance):
        return "%s.%s" % (
            instance.__class__.__name__, event_name)


if settings.RABBITMQ_PUBLISH:
    messaging = RabbitMessaging(MODEL_EXCHANGE_NAME)
    MaaSMessenger(Node, messaging.getExchange()).register()
else:
    messaging = None
