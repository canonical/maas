# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic utilities for dealing with files and the filesystem."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'atomic_symlink',
    'atomic_write',
    'ensure_dir',
    'incremental_write',
    'read_text_file',
    'sudo_write_file',
    'tempdir',
    'write_text_file',
    ]


import codecs
from contextlib import contextmanager
import errno
import os
from os import environ
from os.path import isdir
from shutil import rmtree
from subprocess import (
    PIPE,
    Popen,
    )
import sys
import tempfile
from time import time

from lockfile import FileLock
from provisioningserver.utils import sudo
from provisioningserver.utils.shell import ExternalProcessError


def get_maas_provision_command():
    """Return path to the maas-provision command.

    In production mode this will just return 'maas-provision', but in
    development mode it will return the path for the current development
    environment.
    """
    return environ.get("MAAS_PROVISION_CMD", "maas-provision")


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


def sudo_write_file(filename, contents, encoding='utf-8', mode=0644):
    """Write (or overwrite) file as root.  USE WITH EXTREME CARE.

    Runs an atomic update using non-interactive `sudo`.  This will fail if
    it needs to prompt for a password.
    """
    raw_contents = contents.encode(encoding)
    maas_provision_cmd = get_maas_provision_command()
    command = [
        maas_provision_cmd,
        'atomic-write',
        '--filename', filename,
        '--mode', oct(mode),
        ]
    proc = Popen(sudo(command), stdin=PIPE)
    stdout, stderr = proc.communicate(raw_contents)
    if proc.returncode != 0:
        raise ExternalProcessError(proc.returncode, command, stderr)


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
