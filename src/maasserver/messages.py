# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Messages."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "MAASMessenger",
    "MESSAGING",
    "MessengerBase",
    ]


from abc import (
    ABCMeta,
    abstractmethod,
    )

from django.conf import settings
from django.db.models.signals import (
    post_delete,
    post_save,
    )
from maasserver import logger
from maasserver.exceptions import NoRabbit
from maasserver.json import MAASJSONEncoder
from maasserver.rabbit import RabbitMessaging

# This is the name of the exchange where changes to MAAS's model objects will
# be published.
MODEL_EXCHANGE_NAME = "MAAS Model Exchange"


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

    def publish_message(self, message):
        """Attempt to publish `message` on the producer.

        If RabbitMQ is not available, log an error message but return
        normally.
        """
        try:
            self.producer.publish(message)
        except NoRabbit as e:
            logger.warn("Could not reach RabbitMQ: %s", e)

    def update_obj(self, sender, instance, created, **kwargs):
        event_name = (
            MESSENGER_EVENT.CREATED if created
            else MESSENGER_EVENT.UPDATED)
        self.publish_message(self.create_msg(event_name, instance))

    def delete_obj(self, sender, instance, **kwargs):
        message = self.create_msg(MESSENGER_EVENT.DELETED, instance)
        self.publish_message(message)

    def register(self):
        post_save.connect(
            receiver=self.update_obj, weak=False, sender=self.model_class)
        post_delete.connect(
            receiver=self.delete_obj, weak=False, sender=self.model_class)


class MAASMessenger(MessengerBase):
    """A messenger tailored to suit MAAS' UI (JavaScript) requirements.

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
                "architecture": "i386/generic",
                [...]
            }
        }
    """

    def create_msg(self, event_name, instance):
        event_key = self.event_key(event_name, instance)
        message = MAASJSONEncoder().encode({
            'instance': {
                k: v for k, v in instance.__dict__.items()
                if not k.startswith('_')
            },
            'event_key': event_key,

        })
        return message

    def event_key(self, event_name, instance):
        return "%s.%s" % (
            instance.__class__.__name__, event_name)


class Messaging:
    """Lazy-initialising wrapper for `RabbitMessaging`.

    To access the real `RabbitMessaging` object, call `get`.  On its first
    call it will create the object, and subsequent calls will return the same
    object again.

    :param exchange: Name of the RabbitMQ exchange to which you wish to
        connect.  Defaults to `MODEL_EXCHANGE_NAME`.
    """

    # Sentinel: "cached RabbitMessaging has not been initialised yet."
    UNINITIALISED = object()

    def __init__(self, exchange=MODEL_EXCHANGE_NAME):
        """Create the wrapper, but not the `RabbitMessaging` itself yet."""
        self.exchange = exchange
        self.reset()

    def get(self):
        """Return the actual `RabbitMessaging`, creating it if necessary."""
        if self._cached_messaging is self.UNINITIALISED:
            self._cached_messaging = self._create()
        return self._cached_messaging

    def reset(self):
        """Reset the wrapper to its original, uninitialised state.

        The next call to `get` will initialise a fresh `RabbitMessaging`
        object.
        """
        self._cached_messaging = self.UNINITIALISED

    @staticmethod
    def _create():
        """Create the `RabbitMessaging` object."""
        # Importing this from the top of the module causes AlreadyRegistered
        # errors in tests.
        from maasserver.models import Node

        if settings.RABBITMQ_PUBLISH:
            messaging = RabbitMessaging(MODEL_EXCHANGE_NAME)
            MAASMessenger(Node, messaging.getExchange()).register()
            return messaging
        else:
            return None


# Wrapper for global `RabbitMessaging` object.
MESSAGING = Messaging()
