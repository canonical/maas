# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the provisioning server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ActionScript",
    "asynchronous",
    "atomic_symlink",
    "atomic_write",
    "call_and_check",
    "compose_URL_on_IP",
    "create_node",
    "deferred",
    "ensure_dir",
    "filter_dict",
    "import_settings",
    "incremental_write",
    "locate_config",
    "MainScript",
    "parse_key_value_file",
    "reactor_sync",
    "read_text_file",
    "retries",
    "ShellTemplate",
    "sudo_write_file",
    "synchronous",
    "warn_deprecated",
    "write_custom_config_section",
    "write_text_file",
    ]

from argparse import ArgumentParser
import codecs
from contextlib import contextmanager
import errno
from functools import wraps
import logging
import os
from os import fdopen
from os.path import isdir
from pipes import quote
from shutil import rmtree
import signal
import string
import subprocess
from subprocess import (
    CalledProcessError,
    PIPE,
    Popen,
    )
import sys
from sys import _getframe as getframe
import tempfile
import threading
from time import time
from urlparse import (
    urlparse,
    urlunparse,
    )
from warnings import warn

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
    )
import bson
from crochet import run_in_reactor
from lockfile import FileLock
from lxml import etree
from netaddr import IPAddress
from provisioningserver.auth import get_recorded_api_credentials
from provisioningserver.cluster_config import get_maas_url
import simplejson as json
import tempita
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    maybeDeferred,
    )
from twisted.python import threadable
from twisted.python.threadable import isInIOThread


def node_exists(macs, url, client):
    decoders = {
        "application/json": lambda data: json.loads(data),
        "application/bson": lambda data: bson.BSON(data).decode(),
    }
    params = {
        'mac_address': macs
    }
    response = client.get(url,
                          op='list',
                          **params)
    content = response.read()
    content_type = response.headers.gettype()
    decode = decoders[content_type]
    content = decode(content)
    return len(content) > 0


def create_node(macs, arch, power_type, power_parameters):
    api_credentials = get_recorded_api_credentials()
    if api_credentials is None:
        raise Exception('Not creating node: no API key yet.')
    client = MAASClient(
        MAASOAuth(*api_credentials), MAASDispatcher(),
        get_maas_url())

    data = {
        'architecture': arch,
        'power_type': power_type,
        'power_parameters': json.dumps(power_parameters),
        'mac_addresses': macs,
        'autodetect_nodegroup': 'true'
    }
    url = '/api/1.0/nodes/'
    if node_exists(macs, url, client):
        return
    return client.post(url, 'new', **data)

# A table suitable for use with str.translate() to replace each
# non-printable and non-ASCII character in a byte string with a question
# mark, mimicking the "replace" strategy when encoding and decoding.
non_printable_replace_table = b"".join(
    chr(i) if chr(i) in string.printable else b"?"
    for i in xrange(0xff + 0x01))


class ExternalProcessError(CalledProcessError):
    """Raised when there's a problem calling an external command.

    Unlike `CalledProcessError`:

    - `__str__()` returns a string containing the output of the failed
      external process, if available. All non-printable and non-ASCII
      characters are filtered out, replaced by question marks.

    - `__unicode__()` is defined, and tries to return something
      analagous to `__str__()` but keeping in valid unicode characters
      from the error message.

    """

    @staticmethod
    def _to_unicode(string):
        if isinstance(string, bytes):
            return string.decode("ascii", "replace")
        else:
            return unicode(string)

    @staticmethod
    def _to_ascii(string, table=non_printable_replace_table):
        if isinstance(string, unicode):
            return string.encode("ascii", "replace")
        else:
            return bytes(string).translate(table)

    def __unicode__(self):
        cmd = u" ".join(quote(self._to_unicode(part)) for part in self.cmd)
        output = self._to_unicode(self.output)
        return u"Command `%s` returned non-zero exit status %d:\n%s" % (
            cmd, self.returncode, output)

    def __str__(self):
        cmd = b" ".join(quote(self._to_ascii(part)) for part in self.cmd)
        output = self._to_ascii(self.output)
        return b"Command `%s` returned non-zero exit status %d:\n%s" % (
            cmd, self.returncode, output)

    @property
    def output_as_ascii(self):
        """The command's output as printable ASCII.

        Non-printable and non-ASCII characters are filtered out.
        """
        return self._to_ascii(self.output)

    @property
    def output_as_unicode(self):
        """The command's output as Unicode text.

        Invalid Unicode characters are filtered out.
        """
        return self._to_unicode(self.output)


def call_and_check(command, *args, **kwargs):
    """A wrapper around subprocess.check_call().

    :param command: Command line, as a list of strings.
    :return: The command's output from standard output.
    :raise ExternalProcessError: If the command returns nonzero.
    """
    process = subprocess.Popen(
        command, *args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        **kwargs)
    stdout, stderr = process.communicate()
    stderr = stderr.strip()
    if process.returncode != 0:
        raise ExternalProcessError(process.returncode, command, output=stderr)
    return stdout


def locate_config(*path):
    """Return the location of a given config file or directory.

    Defaults to `/etc/maas` (followed by any further path elements you
    specify), but can be overridden using the `MAAS_CONFIG_DIR` environment
    variable.  (When running from a branch, this variable will point to the
    `etc/maas` inside the branch.)

    The result is absolute and normalized.
    """
    # Check for MAAS_CONFIG_DIR.  Count empty string as "not set."
    env_setting = os.getenv('MAAS_CONFIG_DIR', '')
    if env_setting == '':
        # Running from installed package.  Config is in /etc/maas.
        config_dir = '/etc/maas'
    else:
        # Running from branch or other customized setup.  Config is at
        # $MAAS_CONFIG_DIR/etc/maas.
        config_dir = env_setting

    return os.path.abspath(os.path.join(config_dir, *path))


def find_settings(whence):
    """Return settings from `whence`, which is assumed to be a module."""
    # XXX 2012-10-11 JeroenVermeulen, bug=1065456: Put this in a shared
    # location.  It's currently duplicated from elsewhere.
    return {
        name: value
        for name, value in vars(whence).items()
        if not name.startswith("_")
        }


def import_settings(whence):
    """Import settings from `whence` into the caller's global scope."""
    # XXX 2012-10-11 JeroenVermeulen, bug=1065456: Put this in a shared
    # location.  It's currently duplicated from elsewhere.
    source = find_settings(whence)
    target = sys._getframe(1).f_globals
    target.update(source)


def deferred(func):
    """Decorates a function to ensure that it always returns a `Deferred`.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return maybeDeferred(func, *args, **kwargs)
    return wrapper


def asynchronous(func):
    """Decorates a function to ensure that it always runs in the reactor.

    If the wrapper is called from the reactor thread, it will call
    straight through to the wrapped function. It will not be wrapped by
    `maybeDeferred` for example.

    If the wrapper is called from another thread, it will return a
    :class:`crochet.EventualResult`, as if it had been decorated with
    `crochet.run_in_reactor`.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """
    func_in_reactor = run_in_reactor(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        if isInIOThread():
            return func(*args, **kwargs)
        else:
            return func_in_reactor(*args, **kwargs)
    return wrapper


def synchronous(func):
    """Decorator to ensure that `func` never runs in the reactor thread.

    If the wrapped function is called from the reactor thread, this will
    raise a :class:`AssertionError`, implying that this is a programming
    error. Calls from outside the reactor will proceed unaffected.

    There is an asymmetry with the `asynchronous` decorator. The reason
    is that it is essential to be aware when `deferToThread()` is being
    used, so that in-reactor code knows to synchronise with it, to add a
    callback to the :class:`Deferred` that it returns, for example. The
    expectation with `asynchronous` is that the return value is always
    important, and will be appropriate to the environment in which it is
    utilised.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as synchronous, or blocking.

    :raises AssertionError: When called inside the reactor thread.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # isInIOThread() can return True if the reactor has previously been
        # started but has now stopped, so don't test isInIOThread() until
        # we've also checked if the reactor is running.
        if reactor.running and isInIOThread():
            raise AssertionError(
                "Function %s(...) must not be called in the "
                "reactor thread." % func.__name__)
        else:
            return func(*args, **kwargs)
    return wrapper


@contextmanager
def reactor_sync():
    """Context manager that synchronises with the reactor thread.

    When holding this context the reactor thread is suspended, and the current
    thread is marked as the IO thread. You can then do almost any work that
    you would normally do in the reactor thread.

    The "almost" above refers to things that track state by thread, which with
    Twisted is not much. However, things like :py:mod:`twisted.python.context`
    may not behave quite as you expect.
    """
    # If we're already running in the reactor thread this is a no-op; we're
    # already synchronised with the execution of the reactor.
    if isInIOThread():
        yield
        return

    # If we're not running in the reactor thread, we need to synchronise
    # execution, being careful to avoid deadlocks.
    sync = threading.Condition()
    reactorThread = threadable.ioThread

    # When calling sync.wait() we specify a timeout of sys.maxint. The default
    # timeout of None cannot be interrupted by SIGINT, aka Ctrl-C, which can
    # be more than a little frustrating.

    def sync_io():
        # This runs in the reactor's thread. It first gets a lock on `sync`.
        with sync:
            # This then notifies a single waiter. That waiter will be the
            # thread that this context-manager was invoked from.
            sync.notify()
            # This then waits to be notified back. During this time the
            # reactor cannot run.
            sync.wait(sys.maxint)

    # Grab a lock on the `sync` condition.
    with sync:
        # Schedule `sync_io` to be called in the reactor. We do this with the
        # lock held so that `sync_io` cannot progress quite yet.
        reactor.callFromThread(sync_io)
        # Now, wait. This allows `sync_io` obtain the lock on `sync`, and then
        # awaken me via `notify()`. When `wait()` returns we once again have a
        # lock on `sync`. We're able to get this lock because `sync_io` goes
        # into `sync.wait()`, thus releasing its lock on it.
        sync.wait(sys.maxint)
        try:
            # Mark the current thread as the IO thread. This makes the
            # `asynchronous` and `synchronous` decorators DTRT.
            threadable.ioThread = threadable.getThreadID()
            # Allow this thread to execute while holding `sync`. The reactor
            # is prevented from spinning because `sync_io` is in `wait()`.
            yield
        finally:
            # Restore the IO thread.
            threadable.ioThread = reactorThread
            # Wake up `sync_io`, which can then run to completion, though not
            # until we release our lock `sync` by exiting this context.
            sync.notify()


def filter_dict(dictionary, desired_keys):
    """Return a version of `dictionary` restricted to `desired_keys`.

    This is like a set union, except the values from `dictionary` come along.
    (Actually `desired_keys` can be a `dict`, but its values will be ignored).
    """
    return {
        key: value
        for key, value in dictionary.items()
        if key in desired_keys
    }


def _write_temp_file(content, filename):
    """Write the given `content` in a temporary file next to `filename`."""
    # Write the file to a temporary place (next to the target destination,
    # to ensure that it is on the same filesystem).
    directory = os.path.dirname(filename)
    prefix = ".%s." % os.path.basename(filename)
    suffix = ".tmp"
    try:
        temp_fd, temp_file = tempfile.mkstemp(
            dir=directory, suffix=suffix, prefix=prefix)
    except OSError, error:
        if error.filename is None:
            error.filename = os.path.join(
                directory, prefix + "XXXXXX" + suffix)
        raise
    else:
        with os.fdopen(temp_fd, "wb") as f:
            f.write(content)
            # Finish writing this file to the filesystem, and then, tell the
            # filesystem to push it down onto persistent storage.  This
            # prevents a nasty hazard in aggressively optimized filesystems
            # where you replace an old but consistent file with a new one that
            # is still in cache, and lose power before the new file can be made
            # fully persistent.
            # This was a particular problem with ext4 at one point; it may
            # still be.
            f.flush()
            os.fsync(f)
        return temp_file


def atomic_write(content, filename, overwrite=True, mode=0600):
    """Write `content` into the file `filename` in an atomic fashion.

    This requires write permissions to the directory that `filename` is in.
    It creates a temporary file in the same directory (so that it will be
    on the same filesystem as the destination) and then renames it to
    replace the original, if any.  Such a rename is atomic in POSIX.

    :param overwrite: Overwrite `filename` if it already exists?  Default
        is True.
    :param mode: Access permissions for the file, if written.
    """
    temp_file = _write_temp_file(content, filename)
    os.chmod(temp_file, mode)
    try:
        if overwrite:
            os.rename(temp_file, filename)
        else:
            lock = FileLock(filename)
            lock.acquire()
            try:
                if not os.path.isfile(filename):
                    os.rename(temp_file, filename)
            finally:
                lock.release()
    finally:
        if os.path.isfile(temp_file):
            os.remove(temp_file)


def atomic_symlink(source, name):
    """Create a symbolic link pointing to `source` named `name`.

    This method is meant to be a drop-in replacement of os.symlink.

    The symlink creation will be atomic.  If a file/symlink named
    `name` already exists, it will be overwritten.
    """
    temp_file = '%s.new' % name
    try:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        os.symlink(source, temp_file)
        os.rename(temp_file, name)
    finally:
        if os.path.isfile(temp_file):
            os.remove(temp_file)


def incremental_write(content, filename, mode=0600):
    """Write the given `content` into the file `filename` and
    increment the modification time by 1 sec.

    :param mode: Access permissions for the file.
    """
    old_mtime = get_mtime(filename)
    atomic_write(content, filename, mode=mode)
    new_mtime = pick_new_mtime(old_mtime)
    os.utime(filename, (new_mtime, new_mtime))


def get_mtime(filename):
    """Return a file's modification time, or None if it does not exist."""
    try:
        return os.stat(filename).st_mtime
    except OSError as e:
        if e.errno == errno.ENOENT:
            # File does not exist.  Be helpful, return None.
            return None
        else:
            # Other failure.  The caller will want to know.
            raise


def pick_new_mtime(old_mtime=None, starting_age=1000):
    """Choose a new modification time for a file that needs it updated.

    This function is used to manage the modification time of files
    for which we need to see an increment in the modification time
    each time the file is modified.  This is the case for DNS zone
    files which only get properly reloaded if BIND sees that the
    modification time is > to the time it has in its database.

    Modification time can have a resolution as low as one second in
    some relevant environments (we have observed this with ext3).
    To produce mtime changes regardless, we set a file's modification
    time in the past when it is first written, and
    increment it by 1 second on each subsequent write.

    However we also want to be careful not to set the modification time
    in the future, mostly because BIND does not deal with that very
    well.

    :param old_mtime: File's previous modification time, as a number
        with a unity of one second, or None if it did not previously
        exist.
    :param starting_age: If the file did not exist previously, set its
        modification time this many seconds in the past.
    """
    now = time()
    if old_mtime is None:
        # File is new.  Set modification time in the past to have room for
        # sub-second modifications.
        return now - starting_age
    elif old_mtime + 1 <= now:
        # There is room to increment the file's mtime by one second
        # without ending up in the future.
        return old_mtime + 1
    else:
        # We can't increase the file's modification time.  Give up and
        # return the previous modification time.
        return old_mtime


def split_lines(input, separator):
    """Split each item from `input` into a key/value pair."""
    return (line.split(separator, 1) for line in input if line.strip() != '')


def strip_pairs(input):
    """Strip whitespace of each key/value pair in input."""
    return ((key.strip(), value.strip()) for (key, value) in input)


def parse_key_value_file(file_name, separator=":"):
    """Parse a text file into a dict of key/value pairs.

    Use this for simple key:value or key=value files. There are no
    sections, as required for python's ConfigParse. Whitespace and empty
    lines are ignored.

    :param file_name: Name of file to parse.
    :param separator: The text that separates each key from its value.
    """
    with open(file_name, 'rb') as input:
        return dict(strip_pairs(split_lines(input, separator)))


# Header and footer comments for MAAS custom config sections, as managed
# by write_custom_config_section.
maas_custom_config_markers = (
    "## Begin MAAS settings.  Do not edit; MAAS will overwrite this section.",
    "## End MAAS settings.",
    )


def find_list_item(item, in_list, starting_at=0):
    """Return index of `item` in `in_list`, or None if not found."""
    try:
        return in_list.index(item, starting_at)
    except ValueError:
        return None


def write_custom_config_section(original_text, custom_section):
    """Insert or replace a custom section in a configuration file's text.

    This allows you to rewrite configuration files that are not owned by
    MAAS, but where MAAS will have one section for its own settings.  It
    doesn't read or write any files; this is a pure text operation.

    Appends `custom_section` to the end of `original_text` if there was no
    custom MAAS section yet.  Otherwise, replaces the existing custom MAAS
    section with `custom_section`.  Returns the new text.

    Assumes that the configuration file's format accepts lines starting with
    hash marks (#) as comments.  The custom section will be bracketed by
    special marker comments that make it clear that MAAS wrote the section
    and it should not be edited by hand.

    :param original_text: The config file's current text.
    :type original_text: unicode
    :param custom_section: Custom config section to insert.
    :type custom_section: unicode
    :return: New config file text.
    :rtype: unicode
    """
    header, footer = maas_custom_config_markers
    lines = original_text.splitlines()
    header_index = find_list_item(header, lines)
    if header_index is not None:
        footer_index = find_list_item(footer, lines, header_index)
        if footer_index is None:
            # There's a header but no footer.  Pretend we didn't see the
            # header; just append a new custom section at the end.  Any
            # subsequent rewrite will replace the part starting at the
            # header and ending at the header we will add here.  At that
            # point there will be no trace of the strange situation
            # left.
            header_index = None

    if header_index is None:
        # There was no MAAS custom section in this file.  Append it at
        # the end.
        lines += [
            header,
            custom_section,
            footer,
            ]
    else:
        # There is a MAAS custom section in the file.  Replace it.
        lines = (
            lines[:(header_index + 1)] +
            [custom_section] +
            lines[footer_index:])

    return '\n'.join(lines) + '\n'


def sudo_write_file(filename, contents, encoding='utf-8', mode=0644):
    """Write (or overwrite) file as root.  USE WITH EXTREME CARE.

    Runs an atomic update using non-interactive `sudo`.  This will fail if
    it needs to prompt for a password.
    """
    raw_contents = contents.encode(encoding)
    command = [
        'sudo', '-n', 'maas-provision', 'atomic-write',
        '--filename', filename,
        '--mode', oct(mode),
        ]
    proc = Popen(command, stdin=PIPE)
    stdout, stderr = proc.communicate(raw_contents)
    if proc.returncode != 0:
        raise ExternalProcessError(proc.returncode, command, stderr)


class Safe:
    """An object that is safe to render as-is."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "<%s %r>" % (
            self.__class__.__name__, self.value)


def escape_py_literal(string):
    """Escape and quote a string for use as a python literal."""
    return repr(string).decode('ascii')


class ShellTemplate(tempita.Template):
    """A Tempita template specialised for writing shell scripts.

    By default, substitutions will be escaped using `pipes.quote`, unless
    they're marked as safe. This can be done using Tempita's filter syntax::

      {{foobar|safe}}

    or as a plain Python expression::

      {{safe(foobar)}}

    """

    default_namespace = dict(
        tempita.Template.default_namespace,
        safe=Safe)

    def _repr(self, value, pos):
        """Shell-quote the value by default."""
        rep = super(ShellTemplate, self)._repr
        if isinstance(value, Safe):
            return rep(value.value, pos)
        else:
            return quote(rep(value, pos))


class ActionScript:
    """A command-line script that follows a command+verb pattern."""

    def __init__(self, description):
        super(ActionScript, self).__init__()
        # See http://docs.python.org/release/2.7/library/argparse.html.
        self.parser = ArgumentParser(description=description)
        self.subparsers = self.parser.add_subparsers(title="actions")

    @staticmethod
    def setup():
        # Ensure stdout and stderr are line-bufferred.
        sys.stdout = fdopen(sys.stdout.fileno(), "ab", 1)
        sys.stderr = fdopen(sys.stderr.fileno(), "ab", 1)
        # Run the SIGINT handler on SIGTERM; `svc -d` sends SIGTERM.
        signal.signal(signal.SIGTERM, signal.default_int_handler)

    def register(self, name, handler, *args, **kwargs):
        """Register an action for the given name.

        :param name: The name of the action.
        :param handler: An object, a module for example, that has `run` and
            `add_arguments` callables. The docstring of the `run` callable is
            used as the help text for the newly registered action.
        :param args: Additional positional arguments for the subparser_.
        :param kwargs: Additional named arguments for the subparser_.

        .. _subparser:
          http://docs.python.org/
            release/2.7/library/argparse.html#sub-commands
        """
        parser = self.subparsers.add_parser(
            name, *args, help=handler.run.__doc__, **kwargs)
        parser.set_defaults(handler=handler)
        handler.add_arguments(parser)
        return parser

    def execute(self, argv=None):
        """Execute this action.

        This is intended for in-process invocation of an action, though it may
        still raise L{SystemExit}. The L{__call__} method is intended for when
        this object is executed as a script proper.
        """
        args = self.parser.parse_args(argv)
        args.handler.run(args)

    def __call__(self, argv=None):
        try:
            self.setup()
            self.execute(argv)
        except CalledProcessError as error:
            # Print error.cmd and error.output too?
            raise SystemExit(error.returncode)
        except KeyboardInterrupt:
            raise SystemExit(1)
        else:
            raise SystemExit(0)


class MainScript(ActionScript):
    """An `ActionScript` that always accepts a `--config-file` option.

    The `--config-file` option defaults to the value of
    `MAAS_PROVISIONING_SETTINGS` in the process's environment, or absent
    that, `$MAAS_CONFIG_DIR/pserv.yaml` (normally /etc/maas/pserv.yaml for
    packaged installations, or when running from branch, the equivalent
    inside that branch).
    """

    def __init__(self, description):
        # Avoid circular imports.
        from provisioningserver.config import Config

        super(MainScript, self).__init__(description)
        self.parser.add_argument(
            "-c", "--config-file", metavar="FILENAME",
            help="Configuration file to load [%(default)s].",
            default=Config.DEFAULT_FILENAME)


class AtomicWriteScript:
    """Wrap the atomic_write function turning it into an ActionScript.

    To use:
    >>> main = MainScript(atomic_write.__doc__)
    >>> main.register("myscriptname", AtomicWriteScript)
    >>> main()
    """

    @staticmethod
    def add_arguments(parser):
        """Initialise options for writing files atomically.

        :param parser: An instance of :class:`ArgumentParser`.
        """
        parser.add_argument(
            "--no-overwrite", action="store_true", required=False,
            default=False, help="Don't overwrite file if it exists")
        parser.add_argument(
            "--filename", action="store", required=True, help=(
                "The name of the file in which to store contents of stdin"))
        parser.add_argument(
            "--mode", action="store", required=False, default=None, help=(
                "They permissions to set on the file. If not set "
                "will be r/w only to owner"))

    @staticmethod
    def run(args):
        """Take content from stdin and write it atomically to a file."""
        content = sys.stdin.read()
        if args.mode is not None:
            mode = int(args.mode, 8)
        else:
            mode = 0600
        atomic_write(
            content, args.filename, overwrite=not args.no_overwrite,
            mode=mode)


def ensure_dir(path):
    """Do the equivalent of `mkdir -p`, creating `path` if it didn't exist."""
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
        if not isdir(path):
            # Path exists, but isn't a directory.
            raise
        # Otherwise, the error is that the directory already existed.
        # Which is actually success.


@contextmanager
def tempdir(suffix=b'', prefix=b'maas-', location=None):
    """Context manager: temporary directory.

    Creates a temporary directory (yielding its path, as `unicode`), and
    cleans it up again when exiting the context.

    The directory will be readable, writable, and searchable only to the
    system user who creates it.

    >>> with tempdir() as playground:
    ...     my_file = os.path.join(playground, "my-file")
    ...     with open(my_file, 'wb') as handle:
    ...         handle.write(b"Hello.\n")
    ...     files = os.listdir(playground)
    >>> files
    [u'my-file']
    >>> os.path.isdir(playground)
    False
    """
    path = tempfile.mkdtemp(suffix, prefix, location)
    if isinstance(path, bytes):
        path = path.decode(sys.getfilesystemencoding())
    assert isinstance(path, unicode)
    try:
        yield path
    finally:
        rmtree(path, ignore_errors=True)


def read_text_file(path, encoding='utf-8'):
    """Read and decode the text file at the given path."""
    with codecs.open(path, encoding=encoding) as infile:
        return infile.read()


def write_text_file(path, text, encoding='utf-8'):
    """Write the given unicode text to the given file path.

    If the file existed, it will be overwritten.
    """
    with codecs.open(path, 'w', encoding) as outfile:
        outfile.write(text)


def is_compiled_xpath(xpath):
    """Is `xpath` a compiled expression?"""
    return isinstance(xpath, etree.XPath)


def is_compiled_doc(doc):
    """Is `doc` a compiled XPath document evaluator?"""
    return isinstance(doc, etree.XPathDocumentEvaluator)


def match_xpath(xpath, doc):
    """Return a match of expression `xpath` against document `doc`.

    :type xpath: Either `unicode` or `etree.XPath`
    :type doc: Either `etree._ElementTree` or `etree.XPathDocumentEvaluator`

    :rtype: bool
    """
    is_xpath_compiled = is_compiled_xpath(xpath)
    is_doc_compiled = is_compiled_doc(doc)

    if is_xpath_compiled and is_doc_compiled:
        return doc(xpath.path)
    elif is_xpath_compiled:
        return xpath(doc)
    elif is_doc_compiled:
        return doc(xpath)
    else:
        return doc.xpath(xpath)


def try_match_xpath(xpath, doc, logger=logging):
    """See if the XPath expression matches the given XML document.

    Invalid XPath expressions are logged, and are returned as a
    non-match.

    :type xpath: Either `unicode` or `etree.XPath`
    :type doc: Either `etree._ElementTree` or `etree.XPathDocumentEvaluator`

    :rtype: bool
    """
    try:
        # Evaluating an XPath expression against a document with LXML
        # can return a list or a string, and perhaps other types.
        # Casting the return value into a boolean context appears to
        # be the most reliable way of detecting a match.
        return bool(match_xpath(xpath, doc))
    except etree.XPathEvalError as error:
        # Get a plaintext version of `xpath`.
        expr = xpath.path if is_compiled_xpath(xpath) else xpath
        logger.warning("Invalid expression '%s': %s", expr, unicode(error))
        return False


def classify(func, subjects):
    """Classify `subjects` according to `func`.

    Splits `subjects` into two lists: one for those which `func`
    returns a truth-like value, and one for the others.

    :param subjects: An iterable of `(ident, subject)` tuples, where
        `subject` is an argument that can be passed to `func` for
        classification.
    :param func: A function that takes a single argument.

    :return: A ``(matched, other)`` tuple, where ``matched`` and
        ``other`` are `list`s of `ident` values; `subject` values are
        not returned.
    """
    matched, other = [], []
    for ident, subject in subjects:
        bucket = matched if func(subject) else other
        bucket.append(ident)
    return matched, other


def compose_URL_on_IP(base_url, host):
    """Produce a URL referring to a host by IP address.

    This is straightforward if the IP address is an IPv4 address; but if it's
    an IPv6 address, the URL must contain the IP address in square brackets as
    per RFC 3986.

    :param base_url: URL without the host part, e.g. `http:///path'.
    :param host: IP address to insert in the host part of the URL.
    :return: A URL string with the host part taken from `host`, and all others
        from `base_url`.
    """
    if IPAddress(host).version == 6:
        netloc_host = '[%s]' % host
    else:
        netloc_host = host
    parsed_url = urlparse(base_url)
    if parsed_url.port is None:
        netloc = netloc_host
    else:
        netloc = '%s:%d' % (netloc_host, parsed_url.port)
    return urlunparse(parsed_url._replace(netloc=netloc))


def map_enum(enum_class):
    """Map out an enumeration class as a "NAME: value" dict."""
    # Filter out anything that starts with '_', which covers private and
    # special methods.  We can make this smarter later if we start using
    # a smarter enumeration base class etc.  Or if we switch to a proper
    # enum mechanism, this function will act as a marker for pieces of
    # code that should be updated.
    return {
        key: value
        for key, value in vars(enum_class).items()
        if not key.startswith('_')
    }


def map_enum_reverse(enum_class, ignore=None):
    """Like map_enum(), but reverse its keys and values so you can lookup
    text representations from the enum's integer value.

    Any values in `ignore` are left out of the returned dict.
    """
    if ignore is None:
        ignore = []
    return dict([
        (v, k) for k, v in map_enum(enum_class).viewitems()
        if k not in ignore])


def retries(timeout=30, interval=1, clock=reactor):
    """Helper for retrying something, sleeping between attempts.

    Yields ``(elapsed, remaining, wait)`` tuples, giving times in
    seconds. The last item, `wait`, is the suggested amount of time to
    sleep before trying again.

    @param timeout: From now, how long to keep iterating, in seconds.
    @param interval: The sleep between each iteration, in seconds.
    @param clock: An optional `IReactorTime` provider. Defaults to the
        installed reactor.

    """
    start = clock.seconds()
    end = start + timeout
    while True:
        now = clock.seconds()
        if now < end:
            wait = min(interval, end - now)
            yield now - start, end - now, wait
        else:
            break


def pause(duration, clock=reactor):
    """Pause execution for `duration` seconds.

    Returns a `Deferred` that will fire after `duration` seconds.
    """
    d = Deferred(lambda d: dc.cancel())
    dc = clock.callLater(duration, d.callback, None)
    return d


def warn_deprecated(alternative=None):
    """Issue a `DeprecationWarning` for the calling function.

    :param alternative: Text describing an alternative to using this
        deprecated function.
    """
    target = getframe(1).f_code.co_name
    message = "%s is deprecated" % target
    if alternative is None:
        message = "%s." % (message,)
    else:
        message = "%s; %s" % (message, alternative)
    warn(message, DeprecationWarning, 1)
