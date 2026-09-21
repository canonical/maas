# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Represents the currently logged-in user with their permissions.

    Attributes:
        id (int): the user ID
        username (str): the username of the user
    """

    id: int
    username: str
