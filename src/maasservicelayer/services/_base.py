#  Copyright 2023-2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection


class Service:
    """Base class for services."""

    def __init__(self, connection: AsyncConnection):
        self.conn = connection
