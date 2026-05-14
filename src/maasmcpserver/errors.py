# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


class MAASUnreachableError(Exception):
    """Raised when MAAS endpoint is unreachable."""

    def __init__(self, url_pattern: str, failure_mode: str):
        self.url_pattern = url_pattern
        self.failure_mode = failure_mode  # "timeout" or "connection_refused"
        super().__init__(f"MAAS unreachable: {url_pattern} ({failure_mode})")


class MAASPermissionError(Exception):
    """Raised when user lacks permission to access a resource."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Permission denied (HTTP {status_code})")
