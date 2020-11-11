# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Event-related utilities."""


class Event:
    """Simple event that when fired calls all of the registered handlers on
    this event."""

    def __init__(self):
        self.handlers = set()

    def registerHandler(self, handler):
        """Register handler to event."""
        self.handlers.add(handler)

    def unregisterHandler(self, handler):
        """Unregister handler from event."""
        self.handlers.discard(handler)

    def fire(self, *args, **kwargs):
        """Fire the event."""
        # Shallow-copy the set to avoid "size changed during iteration"
        # errors. This is a fast operation: faster than switching to an
        # immutable set or using thread-safe locks (and won't deadlock).
        for handler in self.handlers.copy():
            handler(*args, **kwargs)


class EventGroup:
    """Group of events.

    Provides a quick way of creating a group of events for an object. Access
    the events as properties on this object.

    Example:
        events = EventGroup("connected", "disconnected")
        events.connected.fire()
        events.disconnected.fire()
    """

    def __init__(self, *events):
        for event in events:
            setattr(self, event, Event())
