# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Fake, synchronous Cobbler XMLRPC service for testing."""

__metaclass__ = type
__all__ = [
    'FakeCobbler',
    'FakeTwistedProxy',
    'fake_token',
    'make_fake_cobbler_session',
    ]

from copy import deepcopy
from fnmatch import fnmatch
from itertools import count
from random import randint
from xmlrpclib import (
    dumps,
    Fault,
    )

from provisioningserver.cobblerclient import CobblerSession
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )


unique_ints = count(randint(0, 99999))


def fake_token(user=None, custom_id=None):
    """Make up a fake auth token.

    :param user: Optional user name to embed in the token id.
    :param custom_id: Optional custom id element to embed in the token id,
        for ease of debugging.
    """
    elements = ['token', '%s' % next(unique_ints), user, custom_id]
    return '-'.join(filter(None, elements))


class FakeTwistedProxy:
    """Fake Twisted XMLRPC proxy that forwards calls to a `FakeCobbler`."""

    def __init__(self, fake_cobbler=None):
        if fake_cobbler is None:
            fake_cobbler = FakeCobbler()
        self.fake_cobbler = fake_cobbler

    @inlineCallbacks
    def callRemote(self, method, *args):
        # Dump the call information as an XML-RPC request to ensure that it
        # will travel over the wire. Cobbler does not allow None so we forbid
        # it here too.
        dumps(args, method, allow_none=False)
        # Continue to forward the call to fake_cobbler.
        callee = getattr(self.fake_cobbler, method, None)
        assert callee is not None, "Unknown Cobbler method: %s" % method
        result = yield callee(*args)
        returnValue(result)


class FakeCobbler:
    """Fake implementation of the Cobbler XMLRPC API.

    This does nothing useful, but tries to be internally consistent and
    similar in use to a real Cobbler instance.  Override as needed.

    Public methods in this class represent Cobbler API calls, except ones
    whose names start with `fake_`.  Call those directly as needed, without
    going through XMLRPC.

    :ivar passwords: A dict mapping user names to their passwords.
    :ivar tokens: Current authentication tokens, mapped to user names.
    :ivar store: Store of Cobbler objects specific to each logged-in token,
        or special value `None` for objects that have been saved to the
        simulated Cobbler database.  Address this dict as
        `store[token][object_type][handle][attribute]`.
    :ivar system_power: Last power action per system handle: 'on', 'off', or
        'reboot'.
    :ivar preseed_templates: A dict mapping preseed templates' paths to
        their contents.
    :ivar preseed_snippets: A dict mapping preseed snippets' paths to
        their contents.
    """
    # Unlike the Cobbler-defined API methods, internal methods take
    # subsets of these parameters, conventionally in this order:
    # 0. self: duh.
    # 1. token: represents a session, with its own local unsaved state.
    # 2. object_type: type to operate on -- distro, system, profile etc.
    # 3. operation: a sub-command to specialize the method further.
    # 4. handle: an object's unique identifier.
    # 5. <other>.
    #
    # Methods whose names start with "_api" are direct implementations
    # of Cobbler API methods.
    def __init__(self, passwords=None):
        """Pretend to be a Cobbler instance.

        :param passwords: A dict mapping user names to their passwords.
        """
        if passwords is None:
            self.passwords = {}
        else:
            self.passwords = passwords

        self.tokens = {}

        # Store of Cobbler objects.  This is a deeply nested dict:
        #  -> token for the session, or None for the saved objects
        #  -> object type (e.g. 'distro' or 'system')
        #  -> handle (assigned by FakeCobbler itself)
        #  -> attribute (an item in an object)
        #  -> value (which in some cases is another dict again).
        self.store = {None: {}}

        self.system_power = {}
        self.preseed_templates = {}
        self.preseed_snippets = {}

    def _check_token(self, token):
        if token not in self.tokens:
            raise Fault(1, "invalid token: %s" % token)

    def _raise_bad_handle(self, object_type, handle):
        raise Fault(1, "Invalid %s handle: %s" % (object_type, handle))

    def _register_type_for_token(self, token, object_type):
        """Make room in dict for `object_type` when used with `token`."""
        self.store.setdefault(token, {}).setdefault(object_type, {})

    def _add_object_to_session(self, token, object_type, handle, obj_dict):
        self._register_type_for_token(token, object_type)
        self.store[token][object_type][handle] = obj_dict

    def _remove_object_from_session(self, token, object_type, handle):
        if handle in self.store.get(token, {}).get(object_type, {}):
            del self.store[token][object_type][handle]

    def _get_object_if_present(self, token, object_type, handle):
        return self.store.get(token, {}).get(object_type, {}).get(handle)

    def _get_handle_if_present(self, token, object_type, name):
        candidates = self.store.get(token, {}).get(object_type, {})
        for handle, candidate in candidates.items():
            if candidate['name'] == name:
                return handle
        return None

    def _matches(self, object_dict, criteria):
        """Does `object_dict` satisfy the constraints in `criteria`?

        :param object_dict: An object in dictionary form, as in the store.
        :param criteria: A dict of constraints.  Each is a glob.
        :return: `True` if, for each key in `criteria`, there is a
            corresponding key in `object_dict` whose value matches the
            glob value as found in `criteria`.
        """
        # Assumption: None matches None.
# TODO: If attribute is a list, match any item in the list.
        return all(
            fnmatch(object_dict.get(key), value)
            for key, value in criteria.items())

    def _api_new_object(self, token, object_type):
        """Create object in the session's local store."""
        self._check_token(token)
        unique_id = next(unique_ints)
        handle = "handle-%s-%d" % (object_type, unique_id)
        name = "name-%s-%d" % (object_type, unique_id)
        new_object = {
            'name': name,
            'comment': (
                "Cobbler stores lots of things we're not interested in; "
                "this comment is here to break tests that let Cobbler's "
                "data leak out of the Provisioning Server."
                ),
        }
        self._add_object_to_session(token, object_type, handle, new_object)
        return handle

    def _api_remove_object(self, token, object_type, name):
        """Remove object from the session and saved stores."""
        # Assumption: removals don't need to be saved.
        self._check_token(token)
        handle = self._api_get_handle(token, object_type, name)
        for session in [token, None]:
            self._remove_object_from_session(session, object_type, handle)

    def _api_get_handle(self, token, object_type, name):
        """Get object handle by name.

        Returns session-local version of the object if available, or
        the saved version otherwise.
        """
        self._check_token(token)
        handle = self._get_handle_if_present(token, object_type, name)
        if handle is None:
            handle = self._get_handle_if_present(None, object_type, name)
        if handle is None:
            raise Fault(1, "Unknown %s: %s." % (object_type, name))
        return handle

    def _api_find_objects(self, object_type, criteria):
        """Find names of objects in the saved store that match `criteria`.

        :return: A list of object names.
        """
        # Assumption: these operations look only at saved objects.
        location = self.store[None].get(object_type, {})
        return [
            candidate['name']
            for candidate in location.values()
                if self._matches(candidate, criteria)]

    def _api_get_object(self, object_type, name):
        """Get object's attributes by name."""
        location = self.store[None].get(object_type, {})
        matches = [obj for obj in location.values() if obj['name'] == name]
        assert len(matches) <= 1, (
            "Multiple %s objects are called '%s'." % (object_type, name))
        if len(matches) == 0:
            return None
        else:
            return deepcopy(matches[0])

    def _api_get_objects(self, object_type):
        """Return all saved objects of type `object_type`.

        :return: A list of object dicts.  The dicts are copied from the
            saved store; they are not references to the originals in the
            store.
        """
        # Assumption: these operations look only at saved objects.
        location = self.store[None].get(object_type, {})
        return [deepcopy(obj) for obj in location.values()]

    def _api_modify_object(self, token, object_type, handle, key, value):
        """Set an attribute on an object.

        The object is copied into the session store if needed; the session
        will see its locally modified version of the object until it saves
        its changes.  At that point, other sessions will get to see it too.
        """
        self._check_token(token)
        session_obj = self._get_object_if_present(token, object_type, handle)
        if session_obj is None:
            # Draw a copy of the saved object into a session-local
            # object.
            saved_obj = self._get_object_if_present(None, object_type, handle)
            if saved_obj is None:
                self._raise_bad_handle(object_type, handle)
            session_obj = deepcopy(saved_obj)
            self._add_object_to_session(
                token, object_type, handle, session_obj)

        session_obj[key] = value

    def _api_save_object(self, token, object_type, handle):
        """Save an object's modifications to the saved store."""
        self._check_token(token)
        saved_obj = self._get_object_if_present(None, object_type, handle)
        session_obj = self._get_object_if_present(token, object_type, handle)

        if session_obj is None and saved_obj is None:
            self._raise_bad_handle(object_type, handle)
        if session_obj is None:
            # Object not modified.  Nothing to do.
            return True

        name = session_obj['name']
        other_handle = self._get_handle_if_present(token, object_type, name)
        if other_handle is not None and other_handle != handle:
            raise Fault(
                1, "The %s name '%s' is already in use."
                % (object_type, name))

        if saved_obj is None:
            self._add_object_to_session(
                None, object_type, handle, session_obj)
        else:
            saved_obj.update(session_obj)

        self._remove_object_from_session(token, object_type, handle)
        return True

    def _api_access_preseed(self, token, read, preseeds_dict, path, contents):
        """Read or write preseed template or snippet."""
        assert read in [True, False], "Invalid 'read' value: %s." % read
        self._check_token(token)
        if read:
            assert contents == '', "Pass empty contents when reading."
        else:
            preseeds_dict[path] = contents
        return preseeds_dict[path]

    def fake_retire_token(self, token):
        """Pretend that `token` has expired."""
        if token in self.store:
            del self.store[token]
        if token in self.tokens:
            del self.tokens[token]

    def fake_system_power(self, handle, power_status):
        """Pretend that the given server has been turned on/off, or rebooted.

        Use this, for example, to simulate completion of a reboot command.

        :param handle: Handle for a system.
        :param power_status: One of 'on', 'off', or 'reboot'.
        """
        self.system_power[handle] = power_status

    def login(self, user, password):
        if password != self.passwords.get(user, object()):
            raise Fault(1, "login failed (%s)" % user)
        token = fake_token(user)
        self.tokens[token] = user
        return token

    def _xapi_edit_system_interfaces(self, token, handle, name, attrs):
        """Edit system interfaces with Cobbler's crazy protocol."""
        obj_state = self._api_get_object('system', name)
        interface_name = attrs.pop("interface")
        interfaces = obj_state.get("interfaces", {})
        if "mac_address" in attrs:
            interface = interfaces.setdefault(interface_name, {})
            interface["mac_address"] = attrs.pop("mac_address")
        elif "delete_interface" in attrs:
            if interface_name in interfaces:
                del interfaces[interface_name]
        else:
            raise AssertionError(
                "Edit operation defined interface but "
                "not mac_address or delete_interface. "
                "Got: %r" % (attrs,))
        self._api_modify_object(
            token, 'system', handle, "interfaces", interfaces)

    def xapi_object_edit(self, object_type, name, operation, attrs, token):
        """Swiss-Army-Knife API: create/rename/copy/edit object."""
        if operation == 'remove':
            self._api_remove_object(token, object_type, name)
            return True
        elif operation == 'add':
            handle = self._api_new_object(token, object_type)
            obj_dict = self.store[token][object_type][handle]
            obj_dict.update(attrs)
            obj_dict['name'] = name
            return self._api_save_object(token, object_type, handle)
        elif operation == 'edit':
            handle = self._api_get_handle(token, object_type, name)
            if object_type == "system" and "interface" in attrs:
                self._xapi_edit_system_interfaces(token, handle, name, attrs)
            for key, value in attrs.items():
                self._api_modify_object(token, object_type, handle, key, value)
            return self._api_save_object(token, object_type, handle)
        else:
            raise NotImplemented(
                "xapi_object_edit(%s, ..., %s, ...)"
                % (object_type, operation))

    def new_distro(self, token):
        return self._api_new_object(token, 'distro')

    def remove_distro(self, name, token, recurse=True):
        self._api_remove_object(token, 'distro', name)

    def get_distro_handle(self, name, token):
        return self._api_get_handle(token, 'distro', name)

    def find_distro(self, criteria):
        return self._api_find_objects('distro', criteria)

    def get_distro(self, name):
        return self._api_get_object('distro', name)

    def get_distros(self):
        return self._api_get_objects('distro')

    def modify_distro(self, handle, key, value, token):
        self._api_modify_object(token, 'distro', handle, key, value)

    def save_distro(self, handle, token):
        return self._api_save_object(token, 'distro', handle)

    def new_image(self, token):
        return self._api_new_object(token, 'image')

    def remove_image(self, name, token, recurse=True):
        self._api_remove_object(token, 'image', name)

    def get_image_handle(self, name, token):
        return self._api_get_handle(token, 'image', name)

    def find_image(self, criteria):
        return self._api_find_objects('image', criteria)

    def get_image(self, name):
        return self._api_get_object('image', name)

    def get_images(self):
        return self._api_get_objects('image')

    def modify_image(self, handle, key, value, token):
        self._api_modify_object(token, 'image', handle, key, value)

    def save_image(self, handle, token):
        return self._api_save_object(token, 'image', handle)

    def new_profile(self, token):
        return self._api_new_object(token, 'profile')

    def remove_profile(self, name, token, recurse=True):
        self._api_remove_object(token, 'profile', name)

    def get_profile_handle(self, name, token):
        return self._api_get_handle(token, 'profile', name)

    def find_profile(self, criteria):
        return self._api_find_objects('profile', criteria)

    def get_profile(self, name):
        return self._api_get_object('profile', name)

    def get_profiles(self):
        return self._api_get_objects('profile')

    def modify_profile(self, handle, key, value, token):
        self._api_modify_object(token, 'profile', handle, key, value)

    def save_profile(self, handle, token):
        return self._api_save_object(token, 'profile', handle)

    def new_repo(self, token):
        return self._api_new_object(token, 'repo')

    def remove_repo(self, name, token, recurse=True):
        self._api_remove_object(token, 'repo', name)

    def get_repo_handle(self, name, token):
        return self._api_get_handle(token, 'repo', name)

    def find_repo(self, criteria):
        return self._api_find_objects('repo', criteria)

    def get_repo(self, name):
        return self._api_get_object('repo', name)

    def get_repos(self):
        return self._api_get_objects('repo')

    def modify_repo(self, handle, key, value, token):
        self._api_modify_object(token, 'repo', handle, key, value)

    def save_repo(self, handle, token):
        return self._api_save_object(token, 'repo', handle)

    def new_system(self, token):
        return self._api_new_object(token, 'system')

    def remove_system(self, name, token, recurse=True):
        self._api_remove_object(token, 'system', name)

    def background_power_system(self, args, token):
        """Asynchronous power on/off/reboot.  No notification."""
        self._check_token(token)
        operation = args['power']
        # This version takes system names.  The regular power_system
        # takes a system handle.
        system_names = args['systems']
        handles = [
            self.get_system_handle(name, token)
            for name in system_names]
        for handle in handles:
            self.power_system(handle, operation, token)

    def get_system_handle(self, name, token):
        return self._api_get_handle(token, 'system', name)

    def find_system(self, criteria):
        return self._api_find_objects('system', criteria)

    def get_system(self, name):
        return self._api_get_object('system', name)

    def get_systems(self):
        return self._api_get_objects('system')

    def modify_system(self, handle, key, value, token):
        self._api_modify_object(token, 'system', handle, key, value)

    def save_system(self, handle, token):
        return self._api_save_object(token, 'system', handle)

    def power_system(self, handle, operation, token):
        self._check_token(token)
        if operation not in ['on', 'off', 'reboot']:
            raise Fault(1, "Invalid power operation: %s." % operation)
        self.system_power[handle] = operation

    def read_or_write_kickstart_template(self, path, read, contents, token):
        return self._api_access_preseed(
            token, read, self.preseed_templates, path, contents)

    def get_kickstart_templates(self, token=None):
        return self.preseed_templates.keys()

    def read_or_write_snippet(self, path, read, contents, token):
        return self._api_access_preseed(
            token, read, self.preseed_snippets, path, contents)

    def get_snippets(self, token=None):
        return self.preseed_snippets.keys()

    def sync(self, token):
        self._check_token(token)


def make_fake_cobbler_session():
    """Return a :class:`CobblerSession` wired up to a :class:`FakeCobbler`."""
    cobbler_session = CobblerSession(
        "http://localhost/does/not/exist", "user", "password")
    cobbler_fake = FakeCobbler({"user": "password"})
    cobbler_proxy = FakeTwistedProxy(cobbler_fake)
    cobbler_session.proxy = cobbler_proxy
    return cobbler_session
