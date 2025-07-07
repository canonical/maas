# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import contextmanager
from shutil import rmtree
from tempfile import mkdtemp
from typing import Iterator


@contextmanager
def tempdir(
    suffix: str = "", prefix: str = "maas-", location: str | None = None
) -> Iterator[str]:
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

    :param suffix: A suffix to append to the temporary directory name.
    :param prefix: A prefix to prepend to the temporary directory name.
    :param location: A directory in which to create the temporary directory.
        If not specified, the system's default temporary directory is used.
    :return: A context manager that yields the path to the temporary directory.
    """
    path = mkdtemp(suffix, prefix, location)
    assert isinstance(path, str)
    try:
        yield path
    finally:
        rmtree(path, ignore_errors=True)
