# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Wrapper for the Cobbler XMLRPC API, using Twisted.

The API looks synchronous, but under the covers, calls yield to the Twisted
reactor so that it can service other callbacks.
"""

__metaclass__ = type
__all__ = [
    'CobblerCommands',
    'CobblerDistro',
    'CobblerImage',
    'CobblerProfile',
    'CobblerSystem',
    ]

import xmlrpclib

from twisted.internet.defer import (
    DeferredLock,
    inlineCallbacks,
    returnValue,
    )
from twisted.web.xmlrpc import Proxy


def looks_like_auth_expiry(exception):
    """Does `exception` look like an authentication token expired?"""
    if not hasattr(exception, 'faultString'):
        # An auth failure would come as an xmlrpclib.Fault.
        return False
    return exception.faultString.startswith("invalid token: ")


class CobblerSession:
    """A session on the Cobbler XMLRPC API.

    The session can be used for many asynchronous requests, all of them
    sharing a single authentication token.
    """

    # In an arguments list, this means "insert security token here."
    token_placeholder = object()

    def __init__(self, url, user, password):
        self.url = url
        self.user = user
        self.password = password
        self.proxy = self._make_twisted_proxy()
        self.token = None
        self.connection_count = 0
        self.authentication_lock = DeferredLock()

    def _make_twisted_proxy(self):
        """Create a Twisted XMRLPC proxy.

        For internal use only, but overridable for test purposes.
        """
# TODO: Is the /RPC2 needed?
        return Proxy(self.url + '/RPC2')

    def record_state(self):
        """Return a cookie representing the session's current state.

        The cookie will change whenever the session is reconnected or
        re-authenticated.  The only valid use of this cookie is to compare
        it for equality with another one.

        If two calls return different cookies, that means that the session
        has broken in some way and been re-established between the two calls.
        """
        return (self.connection_count, self.token)

    @inlineCallbacks
    def authenticate(self, previous_state=None):
        """Log in asynchronously.

        Call this when starting up, but also when an XMLRPC call result
        indicates that the authentication token used for a request has
        expired.

        :param previous_state: The state of the session as recorded by
            `record_state` before the failed request was issued.  If the
            session has had to reconnect or re-authenticate since then, the
            method will assume that a concurrent authentication request has
            completed and the failed request can be retried without logging
            in again.
            If no `previous_state` is given, authentication will happen
            regardless.
        :return: A `Deferred`.
        """
        if previous_state is None:
            previous_state = self.record_state()

        yield self.authentication_lock.acquire()
        try:
            if self.record_state() == previous_state:
                # If we're here, nobody else is authenticating this
                # session.  Clear the stale token as a hint to
                # subsequent calls on the session.  If they see that the
                # session is unauthenticated they won't issue and fail,
                # but rather block for this authentication attempt to
                # complete.
                self.token = None

                # Now initiate our new authentication.
                self.token = yield self.proxy.callRemote(
                    'login', self.user, self.password)
        finally:
            self.authentication_lock.release()

    def substitute_token(self, arg):
        """Return `arg`, or the current auth token for `token_placeholder`."""
        if arg is self.token_placeholder:
            return self.token
        else:
            return arg

    def _issue_call(self, method, *args):
        """Initiate call to XMLRPC method.

        :param method: Name of XMLRPC method to invoke.
        :param *args: Arguments for the call.  If any of them is
            `token_placeholder`, the current security token will be
            substituted in its place.
        :return: `Deferred`.
        """
        args = map(self.substitute_token, args)
        d = self.proxy.callRemote(method, *args)
        return d

    @inlineCallbacks
    def call(self, method, *args):
        """Initiate call to XMLRPC `method` by name, through Twisted.

        Initiates XMLRPC call, yields back to the reactor until it's ready
        with a response, then returns the response.  Use this as if it were
        a synchronous XMLRPC call; but be aware that it lets the reactor run
        other code in the meantime.

        :param method: Name of XMLRPC method to call.
        :param *args: Positional arguments for the XMLRPC call.
        :return: A `Deferred` representing the call.
        """
        original_state = self.record_state()
        authenticate = (self.token_placeholder in args)

        authentication_expired = (authenticate and self.token is None)
        if not authentication_expired:
            # It looks like we're authenticated.  Issue the call.  If we
            # then find out that our authentication token is invalid, we
            # can retry it later.
            try:
                result = yield self._issue_call(method, *args)
            except xmlrpclib.Fault as e:
                if authenticate and looks_like_auth_expiry(e):
                    authentication_expired = True
                else:
                    raise

        if authentication_expired:
            # We weren't authenticated when we started, but we should be
            # now.  Make the final attempt.
            yield self.authenticate(original_state)
            result = yield self._issue_call(method, *args)
        returnValue(result)


class CobblerObject:
    """Abstract base class: a type of object in Cobbler's XMLRPC API.

    Cobbler's API exposes several types of object, but they all conform
    to a very basic standard API.  Implement a type by inheriting from
    this class.

    :ivar object_type: The identifier for the kind of object represented.
        Must be set in concrete derived classes.
    :ivar object_type_plural: Optional plural for the type's identifier.
        If not given, is derived by suffixing `object_type` with an "s".
    :ivar known_attributes: Attributes that this object is known to have.
    """

    # What are objects of this type called in the Cobbler API?
    object_type = None

    # What's the plural of object_type, if not object_type + "s"?
    object_type_plural = None

    # What attributes do we expect to support for this type of object?
    # Only these attributes are allowed.  This is here to force us to
    # keep an accurate record of which attributes we use for which types
    # of objects.  We may find that it helps us catch mistakes, or we
    # may want to let this go once we're comfortable and stable with the
    # API.
    known_attributes = []

    def __init__(self, session, handle=None, name=None, values=None):
        """Reference an object in Cobbler.

        :param session: A `CobblerSession`.
        :param handle: The object's handle, if known.
        :param name: Name for this object, if known.
        :param values: Attribute values for this object, if known.
        """
        if values is None:
            values = {}
        self.session = session
        # Cache the handle; we need it when modifying or saving objects.
        self.handle = handle or values.get('handle')
        # Cache the name; we need it when deleting objects.
        self.name = name or values.get('name')

    @classmethod
    def name_method(cls, name_template, plural=False):
        """Interpolate object_type into a method name template.

        For example, on `CobblerSystem`, "get_%s_handle" would be
        interpolated into "get_system_handle" and "get_%s" with plural=True
        becomes "get_systems".
        """
        if plural:
            type_name = (cls.object_type_plural or '%ss' % cls.object_type)
        else:
            type_name = cls.object_type
        return name_template % type_name

    @classmethod
    @inlineCallbacks
    def retrieve(cls, session, name):
        """Reference an object from Cobbler's database."""
        method = cls.name_method('get_%s_handle')
        handle = yield session.call(method, name, session.token_placeholder)
        returnValue(cls(session, handle, name=name))

    @classmethod
    @inlineCallbacks
    def find(cls, session, **kwargs):
        """Find objects in the database.

        :param session: The `CobblerSession` to operate in.  No authentication
            is required.
        :param **kwargs: Optional search criteria, e.g.
            hostname="*.maas3.example.com" to limit the search to items with
            a hostname attribute that ends in ".maas3.example.com".
        :return: A list of `cls` objects.
        """
        if kwargs:
            method_template = "find_%s"
            args = (kwargs, )
        else:
            method_template = "get_%s"
            args = ()
        method = cls.name_method(method_template, plural=True)
        result = yield session.call(method, *args)
        returnValue([cls(session, values=item) for item in result])

    @classmethod
    @inlineCallbacks
    def new(cls, session):
        """Create an object in Cobbler."""
        method = 'new_%s' % cls.object_type
        handle = yield session.call(method, session.token_placeholder)
        returnValue(cls(session, handle))

    @inlineCallbacks
    def delete(self, recurse=True):
        """Delete this object.  Its name must be known.

        :param recurse: Delete dependent objects recursively?
        """
        assert self.name is not None, (
            "Can't delete %s; don't know its name." % self.object_type)
        method = self.name_method('remove_%s')
        yield self.session.call(
            method, self.name, self.session.token_placeholder, recurse)

    @inlineCallbacks
    def _modify_attributes(self, attributes):
        """Attempt to modify the object's attributes."""
        method = 'modify_%s' % self.object_type
        for key, value in attributes.items():
            assert key in self.known_attributes, (
                "Unknown attribute for %s: %s." % (self.object_type, key))
            yield self.session.call(
                method, self.handle, key, value,
                self.session.token_placeholder)
            if key == 'name':
                self.name = value

    @inlineCallbacks
    def _save_attributes(self):
        """Save object's current state."""
        method = 'modify_%s' % self.object_type
        yield self.session.call(
            method, self.handle, self.session.token_placeholder)

    @inlineCallbacks
    def modify(self, **attributes):
        """Modify this object's attributes, and save.

        :param **attributes: Attribute values to set (as "attribute=value"
            keyword arguments).
        """
        original_state = self.session.record_state()
        yield self._modify_attributes(self, attributes)
        if self.session.record_state() != original_state:
            # Something went wrong and we had to re-authenticate our
            # session while we were modifying attributes.  We can't be sure
            # that our changes all got through, so make them all again.
            original_state = self.session.record_state()
            yield self._modify_attributes(self, attributes)
            if self.session.record_state() != original_state:
                raise RuntimeError(
                    "Cobbler session broke while modifying %s."
                    % self.object_type)

        original_state = self.session.record_state()
        yield self._save_attributes()
        if self.session.record_state() != original_state:
            raise RuntimeError(
                "Cobbler session broke while saving %s." % self.object_type)


class CobblerProfile(CobblerObject):
    """A profile."""
    object_type = 'profile'
    known_attributes = [
        'name',
        ]


class CobblerImage(CobblerObject):
    """An operating system image."""
    object_type = "image"
    known_attributes = [
        'name',
        ]


class CobblerDistro(CobblerObject):
    """A distribution."""
    object_type = 'distro'
    known_attributes = [
        # Path to initrd image:
        'initrd',
        # Path to kernel:
        'kernel',
        # Identifier:
        'name',
        ]


class CobblerSystem(CobblerObject):
    """A computer on the network."""
    object_type = 'system'
    known_attributes = [
        # FQDN:
        'hostname',
        # Space-separated key=value pairs:
        'kernel_options'
        # Space-separated key=value pairs for preseed:
        'ks_meta',
        # A special dict; see below.
        'modify_interface',
        # Unqualified host name:
        'name',
        # Conventionally a distroseries-architecture combo.
        'profile',
        ]

    # The modify_interface dict can contain:
    #  * "macaddress-eth0" etc.
    #  * "ipaddress-eth0" etc.
    #  * "dnsname-eth0" etc.

    @staticmethod
    def get_as_rendered(session, system_name):
        """Return system information in "blended" form.

        The blended form includes information "as koan (or PXE) (or
        templating) would evaluate it."

        I have no idea what this means, but it's in the cobbler API.
        """
        return session.call('get_system_as_rendered', system_name)

    @staticmethod
    def get_changed_systems(session, changed_since):
        """List systems changed since a given time."""
# TODO: Who accounts for the race window?
        seconds_since_epoch = int(changed_since.strftime('%s'))
        return session.call('get_changed_systems', seconds_since_epoch)

    def _callPower(self, operation):
        """Call API's "power_system" method."""
        return self.session.call(
            'power_system', operation, self.session.token_placeholder)

    def powerOn(self):
        """Turn system on."""
        return self._callPower('on')

    def powerOff(self):
        """Turn system on."""
        return self._callPower('off')

    def reboot(self):
        """Turn system on."""
        return self._callPower('reboot')


class CobblerCommands:
    """Other miscellany: grab-bag of API leftovers."""

    def __init__(self, session):
        self.session = session

    def read_preseed_template(self, path):
        """Read a preseed template."""
        return self.session.call(
            'read_or_write_kickstart_template', path, True, '',
            self.session.token_placeholder)

    def write_preseed_template(self, path, contents):
        """Write a preseed template."""
        return self.session.call(
            'read_or_write_kickstart_template', path, False, contents,
            self.session.token_placeholder)

    def read_preseed_snippet(self, path):
        """Read a preseed snippet."""
        return self.session.call(
            'read_or_write_kickstart_snippet', path, True, '',
            self.session.token_placeholder)

    def write_preseed_snippet(self, path, contents):
        """Write a preseed snippet."""
        return self.session.call(
            'read_or_write_kickstart_snippet', path, False, contents,
            self.session.token_placeholder)

    def sync_netboot_configs(self):
        """Update netmasq and tftpd configurations."""
        return self.session.call('sync', self.session.token_placeholder)
