#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel

from maasapiserver.v3.auth.jwt import UserRole


class AuthenticatedUser(BaseModel):
    username: str
    roles: set[UserRole]
