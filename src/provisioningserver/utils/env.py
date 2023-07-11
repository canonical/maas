# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Environment-related utilities."""


from contextlib import contextmanager, suppress
import os
from pathlib import Path
import threading
from typing import Optional

from provisioningserver.path import get_maas_data_path
from provisioningserver.utils.fs import atomic_delete, atomic_write


@contextmanager
def environment_variables(variables):
    """Context manager: temporarily set the given environment variables.

    The variables are reset to their original settings afterwards.

    :param variables: A dict mapping environment variables to their temporary
        values.
    """
    prior_environ = os.environ.copy()
    os.environ.update(variables)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(prior_environ)


class FileBackedValue:
    """A shared value read and written to file.

    The content is written to the specified file under the MAAS data path, and
    access is done through a LockFile.

    """

    def __init__(self, name):
        self.name = name
        self._value = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path()

    def clear_cached(self):
        """Clear cached value so that next get call reads it again from disk."""
        self._value = None

    def get(self) -> Optional[str]:
        """Return the value if set, else None"""
        with self._lock:
            if not self._value:
                if not self.path.exists():
                    return None

                value = self._normalise_value(
                    self.path.read_text(encoding="ascii")
                )
                self._value = value
            return self._value

    def set(self, value: Optional[str]):
        """Set the value.

        If None is passed, the backing file is removed.
        """
        value = self._normalise_value(value)
        with self._lock:
            if value is None:
                with suppress(FileNotFoundError):
                    atomic_delete(self.path)
                self.clear_cached()
            else:
                # ensure the parent dirs exist
                self.path.parent.mkdir(exist_ok=True)
                atomic_write(value.encode("ascii"), self.path, mode=0o640)
                self._value = value

    def _normalise_value(self, value: Optional[str]) -> Optional[str]:
        if value:
            value = value.strip()
        return value if value else None

    def _path(self) -> Path:
        # separate function so that it can be overridden in tests
        return Path(get_maas_data_path(self.name))


MAAS_ID = FileBackedValue("maas_id")
MAAS_UUID = FileBackedValue("maas_uuid")
MAAS_SHARED_SECRET = FileBackedValue("secret")


class GlobalValue:
    """Hold the value for a global variable."""

    def __init__(self):
        self._value = None

    def get(self):
        """Return the value."""
        return self._value

    def set(self, value):
        """Set the value."""
        self._value = value


MAAS_SECRET = GlobalValue()
