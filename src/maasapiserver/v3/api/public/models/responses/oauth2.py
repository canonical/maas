# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel


class AccessTokenResponse(BaseModel):
    """Content for a response returning a JWT."""

    kind = "AccessToken"
    token_type: str
    access_token: str
