# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the provisioning server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "ActionScript",
    "atomic_write",
    "deferred",
    "import_settings",
    "incremental_write",
    "locate_config",
    "MainScript",
    "ensure_dir",
    "parse_key_value_file",
    "read_text_file",
    "ShellTemplate",
    "sudo_write_file",
    "write_custom_config_section",
    "write_text_file",
    ]

from argparse import ArgumentParser
import codecs
import errno
from functools import wraps
import os
from os import fdopen
from os.path import isdir
from pipes import quote
import signal
from subprocess import (
    CalledProcessError,
    PIPE,
    Popen,
    )
import sys
import tempfile
from time import time

from lockfile import FileLock
import netifaces
from provisioningserver.config import Config
import tempita
from twisted.internet.defer import maybeDeferred


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
        raise CalledProcessError(proc.returncode, command, stderr)


class Safe:
    """An object that is safe to render as-is."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "<%s %r>" % (
            self.__class__.__name__, self.value)


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
            "The permissions to set on the file. If not set will be r/w only "
            "to owner"))

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


def get_all_interface_addresses():
    """For each network interface, yield its IPv4 address."""
    for interface in netifaces.interfaces():
        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addresses:
            for inet_address in addresses[netifaces.AF_INET]:
                if "addr" in inet_address:
                    yield inet_address["addr"]


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
