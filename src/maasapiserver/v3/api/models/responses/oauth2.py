from pydantic import BaseModel


class AccessTokenResponse(BaseModel):
    """Content for a response returning a JWT."""

    kind = "AccessToken"
    token_type: str
    access_token: str
