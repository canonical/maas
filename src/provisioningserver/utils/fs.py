# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic utilities for dealing with files and the filesystem."""

__all__ = [
    'atomic_delete',
    'atomic_symlink',
    'atomic_write',
    'ensure_dir',
    'FileLock',
    'incremental_write',
    'read_text_file',
    'RunLock',
    'sudo_delete_file',
    'sudo_write_file',
    'SystemLock',
    'tempdir',
    'write_text_file',
]

from base64 import urlsafe_b64encode
import codecs
from contextlib import contextmanager
import errno
from itertools import count
import os
from os import (
    rename,
    stat,
    chown,
)
from os.path import (
    abspath,
    isdir,
)
from random import randint
from shutil import rmtree
from subprocess import (
    PIPE,
    Popen,
)
import tempfile
import threading
from time import (
    sleep,
    time,
)

from provisioningserver.utils import sudo
from provisioningserver.utils.shell import ExternalProcessError
from provisioningserver.utils.twisted import retries
from twisted.internet import reactor
from twisted.python.filepath import FilePath
from twisted.python.lockfile import FilesystemLock


def get_maas_provision_command():
    """Return path to the maas-provision command.

    In production mode this will just return 'maas-provision', but in
    development mode it will return the path for the current development
    environment.
    """
    # Avoid circular imports.
    from provisioningserver.config import is_dev_environment
    if is_dev_environment():
        from maastesting import root
        return os.path.join(root, "bin", "maas-provision")
    else:
        return "maas-provision"


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
    except OSError as error:
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


def atomic_write(content, filename, overwrite=True, mode=0o600):
    """Write `content` into the file `filename` in an atomic fashion.

    This requires write permissions to the directory that `filename` is in.
    It creates a temporary file in the same directory (so that it will be
    on the same filesystem as the destination) and then renames it to
    replace the original, if any.  Such a rename is atomic in POSIX.

    :param overwrite: Overwrite `filename` if it already exists?  Default
        is True.
    :param mode: Access permissions for the file, if written.
    """
    if not isinstance(content, bytes):
        raise TypeError("Content must be bytes, got: %r" % (content, ))

    temp_file = _write_temp_file(content, filename)
    os.chmod(temp_file, mode)

    # Copy over ownership attributes if file exists
    try:
        prev_stats = stat(filename)
    except OSError as error:
        if error.errno != errno.ENOENT:
            raise  # Something's seriously wrong.
    else:
        chown(temp_file, prev_stats.st_uid, prev_stats.st_gid)

    try:
        if overwrite:
            rename(temp_file, filename)
        else:
            with FileLock(filename):
                if not os.path.isfile(filename):
                    rename(temp_file, filename)
    finally:
        if os.path.isfile(temp_file):
            os.remove(temp_file)


def atomic_delete(filename):
    """Delete the file `filename` in an atomic fashion.

    This requires write permissions to the directory that `filename` is in.
    It moves the file to a temporary file in the same directory (so that it
    will be on the same filesystem as the destination) and then deletes the
    temporary file. Such a rename is atomic in POSIX.
    """
    del_filename = "%s/.%s.del" % (
        os.path.dirname(filename), os.path.basename(filename))
    rename(filename, del_filename)
    os.remove(del_filename)


def create_provisional_symlink(src_dir, dst):
    """Create a temporary symlink in `src_dir` that points to `dst`.

    It will try up to 100 times before it gives up.
    """
    for attempt in count(1):
        rnd = randint(0, 999999)  # Inclusive range.
        src = os.path.join(src_dir, ".temp.%06d" % rnd)
        try:
            os.symlink(dst, src)
        except OSError as error:
            # If we've already tried 100 times to create the
            # symlink, give up, and re-raise the most recent
            # exception.
            if attempt >= 100:
                raise
            # If the symlink already exists we'll try again,
            # otherwise re-raise the current exception.
            if error.errno != errno.EEXIST:
                raise
        else:
            # The symlink was created successfully, so return
            # its full path.
            return src


def atomic_symlink(source, name):
    """Create a symbolic link pointing to `source` named `name`.

    This method is meant to be a drop-in replacement for `os.symlink`.

    The symlink creation will be atomic.  If a file/symlink named
    `name` already exists, it will be overwritten.
    """
    prov = create_provisional_symlink(os.path.dirname(name), source)
    # Move the provisionally created symlink into the desired
    # end location, clobbering any existing link.
    try:
        os.rename(prov, name)
    except:
        # Remove the provisionally created symlink so that
        # garbage does not accumulate.
        os.unlink(prov)
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


def incremental_write(content, filename, mode=0o600):
    """Write the given `content` into the file `filename` and
    increment the modification time by 1 sec.

    :type content: `bytes`
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


def sudo_write_file(filename, contents, mode=0o644):
    """Write (or overwrite) file as root.  USE WITH EXTREME CARE.

    Runs an atomic update using non-interactive `sudo`.  This will fail if
    it needs to prompt for a password.

    :type contents: `bytes`.
    """
    if not isinstance(contents, bytes):
        raise TypeError("Content must be bytes, got: %r" % (contents, ))
    maas_provision_cmd = get_maas_provision_command()
    command = [
        maas_provision_cmd,
        'atomic-write',
        '--filename', filename,
        '--mode', "%.4o" % mode,
    ]
    proc = Popen(sudo(command), stdin=PIPE)
    stdout, stderr = proc.communicate(contents)
    if proc.returncode != 0:
        raise ExternalProcessError(proc.returncode, command, stderr)


def sudo_delete_file(filename):
    """Delete file as root.  USE WITH EXTREME CARE.

    Runs an atomic update using non-interactive `sudo`.  This will fail if
    it needs to prompt for a password.
    """
    maas_provision_cmd = get_maas_provision_command()
    command = [
        maas_provision_cmd,
        'atomic-delete',
        '--filename', filename,
    ]
    proc = Popen(sudo(command))
    stdout, stderr = proc.communicate()
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
def tempdir(suffix='', prefix='maas-', location=None):
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
    assert isinstance(path, str)
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
    with open(path, 'w', encoding=encoding) as outfile:
        outfile.write(text)


class SystemLock:
    """A file-system lock.

    It is also not reentrant, deliberately so, for good reason: if you use
    this to guard against concurrent writing to a file, say, then opening it
    twice in any circumstance is bad news.

    This behaviour comes about by:

    * Taking a process-global lock before performing any file-system
      operations.

    * Using :class:`twisted.python.lockfile.FilesystemLock` under the hood.
      This does not permit double-locking of a file by the name process (or by
      any other process, naturally).

    There are options too:

    * `SystemLock` attempts to lock exactly the file at the path given.

    * `FileLock` attempts to lock the file at the path given with an
      additional suffix of ".lock".

    * `RunLock` attempts to lock a file in ``/run/lock`` with a name based on
      the given path and an optional "pretty" name.

    """

    class NotAvailable(Exception):
        """Something has prevented acquisition of this lock.

        For example, the lock has already been acquired.
        """

    # File-system locks typically claim a lock for the sake of a *process*
    # rather than a *thread within a process*. We use a process-global lock to
    # serialise all file-system lock operations so that only one thread can
    # claim a file-system lock at a time.
    PROCESS_LOCK = threading.Lock()

    def __init__(self, path):
        super(SystemLock, self).__init__()
        self.fslock = FilesystemLock(path)

    def __enter__(self):
        with self.PROCESS_LOCK:
            if not self.fslock.lock():
                raise self.NotAvailable(self.fslock.name)

    def __exit__(self, *exc_info):
        with self.PROCESS_LOCK:
            self.fslock.unlock()

    @contextmanager
    def wait(self, timeout=86400):
        """Wait for the lock to become available.

        :param timeout: The number of seconds to wait. By default it will wait
            up to 1 day.
        """
        interval = max(0.1, min(1.0, float(timeout) / 10.0))

        for _, _, wait in retries(timeout, interval, reactor):
            with self.PROCESS_LOCK:
                if self.fslock.lock():
                    break
            if wait > 0:
                sleep(wait)
        else:
            raise self.NotAvailable(self.fslock.name)

        try:
            yield
        finally:
            with self.PROCESS_LOCK:
                self.fslock.unlock()

    @property
    def path(self):
        return self.fslock.name

    def is_locked(self):
        """Is this lock already taken?

        Use this for informational purposes only.

        The way this works is as follows:

        1. Create a new `FilesystemLock` with the same path.

        2. Use the global process lock to ensure no other processes are also
           trying to access the lock.

        3. Attempt to lock the file-system lock:

           3a. Upon success, we know that the lock must have been unlocked;
               return ``True``.

           3b. Upon failure, no action is required because the lock failed. We
               know that the lock must have been locked; return ``False``.

        """
        fslock = FilesystemLock(self.fslock.name)
        with self.PROCESS_LOCK:
            if fslock.lock():
                fslock.unlock()
                return False
            else:
                return True


class FileLock(SystemLock):
    """Always create a lock file at ``${path}.lock``."""

    def __init__(self, path):
        lockpath = FilePath(path).asTextMode().path + ".lock"
        super(FileLock, self).__init__(lockpath)


def _ensure_bytes(string):
    if isinstance(string, str):
        return string.encode("utf-8")
    elif isinstance(string, bytes):
        return string
    else:
        raise TypeError(
            "unicode/bytes expected, got: %r" % (string, ))


class RunLock(SystemLock):
    """Always create a lock file at ``/run/lock/maas.*.lock``.

    This implements an advisory file lock, by proxy, on the given file-system
    path. This is especially useful if you do not have permissions to the
    directory in which the given path is located.
    """

    def __init__(self, path):
        discriminator = urlsafe_b64encode(abspath(_ensure_bytes(path)))
        lockpath = "/run/lock/maas.%s.lock" % discriminator.decode("ascii")
        super(RunLock, self).__init__(lockpath)
