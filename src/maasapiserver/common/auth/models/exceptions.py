#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).


class BakeryException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class MacaroonApiException(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
