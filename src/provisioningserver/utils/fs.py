# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic utilities for dealing with files and the filesystem."""

import codecs
from contextlib import contextmanager
import errno
import filecmp
from itertools import count
import os
from os import chown, rename, stat
from pathlib import Path
from random import randint
from shutil import copyfile, rmtree
import string
from subprocess import PIPE, Popen
import tempfile
import threading
from time import sleep

from twisted.python.filepath import FilePath
from twisted.python.lockfile import FilesystemLock as TwistedFilesystemLock

from provisioningserver.path import get_data_path, get_path
from provisioningserver.utils import snap, sudo
from provisioningserver.utils.shell import ExternalProcessError
from provisioningserver.utils.twisted import retries


def get_maas_common_command():
    """Return path to the maas-rack command.

    In production mode this will just return 'maas-rack', but in
    development mode it will return the path for the current development
    environment.
    """
    # Avoid circular imports.
    from provisioningserver.config import is_dev_environment

    if is_dev_environment():
        from maastesting import dev_root

        return os.path.join(dev_root, "bin/maas-common")
    elif snap.running_in_snap():
        # there's no maas-common in the snap as maas-rack is always present
        return os.path.join(
            snap.SnapPaths.from_environ().snap, "bin/maas-rack"
        )
    else:
        return get_path("usr/lib/maas/maas-common")


def get_root_path():
    """Return the root of the system

    $SNAP if running in a snap, otherwise /.
    """
    return snap.SnapPaths.from_environ().snap or Path("/")


def get_library_script_path(name):
    """Return path to a "library script".

    By convention (here) scripts are always installed to ``/usr/lib/maas`` on
    the target machine.

    The FHS (Filesystem Hierarchy Standard) defines ``/usr/lib/`` as the
    location for libraries used by binaries in ``/usr/bin`` and ``/usr/sbin``,
    hence the term "library script".

    In production mode this will return ``/usr/lib/maas/$name``, but in
    development mode it will return
    ``$dev_root/package-files/usr/lib/maas/$name``.
    """
    from provisioningserver.config import is_dev_environment

    if is_dev_environment():
        from maastesting import dev_root

        return os.path.join(dev_root, "package-files/usr/lib/maas", name)
    else:
        return os.path.join(get_path("/usr/lib/maas"), name)


def _write_temp_file(content, filename):
    """Write the given `content` in a temporary file next to `filename`."""
    # Write the file to a temporary place (next to the target destination,
    # to ensure that it is on the same filesystem).
    directory = os.path.dirname(filename)
    prefix = ".%s." % os.path.basename(filename)
    suffix = ".tmp"
    try:
        temp_fd, temp_file = tempfile.mkstemp(
            dir=directory, suffix=suffix, prefix=prefix
        )
    except OSError as error:
        if error.filename is None:
            error.filename = os.path.join(
                directory, prefix + "XXXXXX" + suffix
            )
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


def atomic_write(
    content, filename, overwrite=True, mode=0o600, uid=None, gid=None
):
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
        raise TypeError(f"Content must be bytes, got: {content!r}")

    temp_file = _write_temp_file(content, filename)
    os.chmod(temp_file, mode)

    # Copy over ownership attributes if file exists
    try:
        prev_stats = stat(filename)
    except OSError as error:
        if error.errno != errno.ENOENT:
            raise  # Something's seriously wrong.
    else:
        try:
            chown(
                temp_file, uid or prev_stats.st_uid, gid or prev_stats.st_gid
            )
        except PermissionError as error:
            # if the permissions of `filename` couldn't be applied to
            # `temp_file` then the temporary file needs to be removed and then
            # raise the exception to allow the caller handle it (LP: #1883748).
            if os.path.isfile(temp_file):
                os.remove(temp_file)

            raise error

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


def are_identical_files(old, new):
    """Are `old` and `new` identical?

    If `old` does not exist, the two are considered different (`new` is
    assumed to exist).
    """
    if os.path.isfile(old):
        return filecmp.cmp(old, new, shallow=False)
    else:
        return False


def atomic_copy(source, destination):
    """Copy a file at path `source` as `destination` in an atomic fashion.

    copy will be atomic.  If an identical file is already at the destination,
    it will be left untouched.

    :param source: Source path of the file..
    :param destination: Destination path of the file.
    """
    if are_identical_files(destination, source):
        return

    # Copy new file next to the old one, to ensure that it is on the
    # same filesystem.  Once it is, we can replace the old one with an
    # atomic rename operation.
    temp_file = "%s.new" % destination
    if os.path.exists(temp_file):
        os.remove(temp_file)
    copyfile(source, temp_file)
    os.rename(temp_file, destination)


def atomic_delete(filename):
    """Delete the file `filename` in an atomic fashion.

    This requires write permissions to the directory that `filename` is in.
    It moves the file to a temporary file in the same directory (so that it
    will be on the same filesystem as the destination) and then deletes the
    temporary file. Such a rename is atomic in POSIX.
    """
    fd, del_filename = tempfile.mkstemp(
        ".deleted", ".", os.path.dirname(filename)
    )
    try:
        os.close(fd)
        rename(filename, del_filename)
    finally:
        os.remove(del_filename)


def create_provisional_symlink(src_dir, dst):
    """Create a temporary symlink in `src_dir` that points to `dst`.

    It will try up to 100 times before it gives up.
    """
    for attempt in count(1):
        rnd = randint(0, 999999)  # Inclusive range.
        link_name = os.path.join(src_dir, ".temp.%06d" % rnd)
        rel_src = os.path.relpath(dst, os.path.dirname(link_name))
        try:
            os.symlink(rel_src, link_name)
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
            return link_name


def atomic_symlink(source, link_name):
    """Create a symbolic link pointing to `source` named `link_name`.

    This method is meant to be a drop-in replacement for `os.symlink`.

    The symlink creation will be atomic.  If a file/symlink named
    `name` already exists, it will be overwritten.
    """
    prov = create_provisional_symlink(os.path.dirname(link_name), source)
    # Move the provisionally created symlink into the desired
    # end location, clobbering any existing link.
    try:
        os.rename(prov, link_name)
    except Exception:
        # Remove the provisionally created symlink so that
        # garbage does not accumulate.
        os.unlink(prov)
        raise


def incremental_write(content, filename, mode=0o600, uid=None, gid=None):
    """Write the given `content` into the file `filename`.  In the past, this
    would potentially change modification time to arbitrary values.

    :type content: `bytes`
    :param mode: Access permissions for the file.
    """
    # We used to change modification time on the files, in an attempt to out
    # smart BIND into loading zones on file systems where time was not granular
    # enough.  BIND got smarter about how it loads zones and remembers when it
    # last loaded the zone: either the then-current time, or the mtime of the
    # file, whichever is later.  When BIND then gets a reload request, it
    # compares the current time to the loadtime for the domain, and skips it if
    # the file is not new.  If we set mtime in the past, then zones don't load.
    # If we set it in the future, then we WILL sometimes hit the race condition
    # where BIND looks at the time after we atomic_write, but before we manage
    # to set the time into the future.  N.B.: /etc on filesystems with 1-second
    # granularity are no longer supported by MAAS.  The good news is that since
    # 2.6, linux has supported nanosecond-granular time.  As of bind9
    # 1:9.10.3.dfsg.P2-5, BIND even uses it.
    atomic_write(content, filename, mode=mode, uid=uid, gid=gid)


def _with_dev_python(*command):
    # Avoid circular imports.
    from provisioningserver.config import is_dev_environment

    if is_dev_environment():
        from maastesting import dev_root

        interpreter = os.path.join(dev_root, "bin", "py")
        command = interpreter, *command
    return command


def sudo_write_file(filename, contents, mode=0o644):
    """Write (or overwrite) file as root.  USE WITH EXTREME CARE.

    Runs an atomic update using non-interactive `sudo`.  This will fail if
    it needs to prompt for a password.

    When running in a snap or devel mode, this function calls
    `atomic_write` directly.

    :type contents: `bytes`.
    """
    from provisioningserver.config import is_dev_environment

    if not isinstance(contents, bytes):
        raise TypeError(f"Content must be bytes, got: {contents!r}")
    if snap.running_in_snap():
        atomic_write(contents, filename, mode=mode)
    else:
        maas_write_file = get_library_script_path("maas-write-file")
        command = _with_dev_python(maas_write_file, filename, "%.4o" % mode)
        if not is_dev_environment():
            command = sudo(command)
        proc = Popen(command, stdin=PIPE)
        stdout, stderr = proc.communicate(contents)
        if proc.returncode != 0:
            raise ExternalProcessError(proc.returncode, command, stderr)


def sudo_delete_file(filename):
    """Delete file as root.  USE WITH EXTREME CARE.

    Runs an atomic update using non-interactive `sudo`.  This will fail if
    it needs to prompt for a password.

    When running in a snap this function calls `atomic_write` directly.
    """
    from provisioningserver.config import is_dev_environment

    if snap.running_in_snap():
        atomic_delete(filename)
    else:
        maas_delete_file = get_library_script_path("maas-delete-file")
        command = _with_dev_python(maas_delete_file, filename)
        if not is_dev_environment():
            command = sudo(command)
        proc = Popen(command)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            raise ExternalProcessError(proc.returncode, command, stderr)


@contextmanager
def tempdir(suffix="", prefix="maas-", location=None):
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


def read_text_file(path, encoding="utf-8"):
    """Read and decode the text file at the given path."""
    with codecs.open(path, encoding=encoding) as infile:
        return infile.read()


def write_text_file(path, text, encoding="utf-8"):
    """Write the given unicode text to the given file path.

    If the file existed, it will be overwritten.
    """
    with open(path, "w", encoding=encoding) as outfile:
        outfile.write(text)


class FilesystemLock(TwistedFilesystemLock):
    """Patch Twisted's FilesystemLock.lock to handle
    PermissionError when trying to lock."""

    def lock(self):
        try:
            return super().lock()
        except PermissionError:
            # LP: #1847794
            # The issue seems to be that the networking monitoring services
            # has a lock file to ensure that only one processes updates the
            # networking information. If the processes gets killed, the lock
            # file stays, pointing to the PID the killed regiond process had.

            # Now what normally happens is that another process tries to
            # acquire the lock, sees that the lock points to a killed PID,
            # and recreates the lock.

            # This normally works, but what can happen is that the killed PID
            # gets recycled, so that the lock now points to a PID which the
            # maas user isn't allowed to kill. Now a PermissionError is raised,
            # that the lock file implementation doesn't handle this case, and
            # the networking monitoring service can never start.

            # Remove the current lock file and retry.
            os.remove(self.name)
            return super().lock()


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

    * `SystemLock` uses the given path as its lock file. This is the most
      general lock.

    * `FileLock` adds a suffix of ".lock" to the given path and uses that as
      its lock file. Use this when updating a file in a writable directory,
      for example.

    * `RunLock` puts its lock file in ``/run/lock`` with a distinctive name
      based on the given path. Use this when updating a file in a non-writable
      directory, for example.

    * `NamedLock` also puts its lock file in ``/run/lock`` but with a name
      based on the given _name_. `NamedLock`'s lock file are named in such a
      way that they will never conflict with a `RunLock`'s. Use this to
      synchronise between processes on a single host, for example, where
      synchronisation does not naturally revolve around access to a specific
      file.

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

    def __init__(self, path, reactor=None):
        super().__init__()
        self._fslock = FilesystemLock(path)
        self.reactor = reactor
        if self.reactor is None:
            from twisted.internet import reactor

            self.reactor = reactor

    def __enter__(self):
        self.acquire()

    def __exit__(self, *exc_info):
        self.release()

    def acquire(self):
        """Acquire the lock.

        :raise NotAvailable: When the lock has already been acquired.
        """
        with self.PROCESS_LOCK:
            if not self._fslock.lock():
                raise self.NotAvailable(self._fslock.name)

    def release(self):
        """Release the lock."""
        with self.PROCESS_LOCK:
            self._fslock.unlock()

    @contextmanager
    def wait(self, timeout=86400):
        """Wait for the lock to become available.

        :param timeout: The number of seconds to wait. By default it will wait
            up to 1 day.
        """
        interval = max(0.1, min(1.0, float(timeout) / 10.0))

        for _, _, wait in retries(timeout, interval, self.reactor):
            with self.PROCESS_LOCK:
                if self._fslock.lock():
                    break
            if wait > 0:
                sleep(wait)
        else:
            raise self.NotAvailable(self._fslock.name)

        try:
            yield
        finally:
            with self.PROCESS_LOCK:
                self._fslock.unlock()

    @property
    def path(self):
        return self._fslock.name

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
        fslock = FilesystemLock(self._fslock.name)
        with self.PROCESS_LOCK:
            if fslock.lock():
                fslock.unlock()
                return False
            else:
                return True


class FileLock(SystemLock):
    """Always create a lock file at ``${path}.lock``."""

    def __init__(self, path, reactor=None):
        lockpath = FilePath(path).asTextMode().path + ".lock"
        super().__init__(lockpath, reactor=reactor)


class RunLock(SystemLock):
    """Lock file at ``${MAAS_ROOT}/run/lock/maas@${path,modified}``.

    This implements an advisory file lock, by proxy, on the given file-system
    path. This is especially useful if you do not have permissions to the
    directory in which the given path is located.

    The path will be made absolute, colons will be replaced with two colons,
    and forward slashes will be replaced with colons.
    """

    def __init__(self, path, reactor=None):
        abspath = FilePath(path).asTextMode().path.lstrip("/")
        discriminator = abspath.replace(":", "::").replace("/", ":")
        lockpath = get_data_path("run", "lock", "maas@%s" % discriminator)
        super().__init__(lockpath, reactor=reactor)


class NamedLock(SystemLock):
    """Lock file at ``${MAAS_ROOT}/run/lock/maas.${name}``.

    This implements an advisory lock, by proxy, for an abstract name. The name
    must be a string and can contain only numerical digits, hyphens, and ASCII
    letters.
    """

    ACCEPTABLE_CHARACTERS = frozenset().union(
        string.ascii_letters, string.digits, "-"
    )

    def __init__(self, name, reactor=None):
        if not isinstance(name, str):
            raise TypeError(
                "Lock name must be str, not %s" % type(name).__qualname__
            )
        elif not self.ACCEPTABLE_CHARACTERS.issuperset(name):
            illegal = set(name) - self.ACCEPTABLE_CHARACTERS
            raise ValueError(
                "Lock name contains illegal characters: %s"
                % "".join(sorted(illegal))
            )
        else:
            lockpath = get_data_path("run", "lock", "maas:%s" % name)
            super().__init__(lockpath, reactor=reactor)
