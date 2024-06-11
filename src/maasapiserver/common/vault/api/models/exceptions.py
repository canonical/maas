#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).


class VaultException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class VaultAuthenticationException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class VaultPermissionsException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class VaultNotFoundException(Exception):
    def __init__(self, message: str):
        super().__init__(message)
