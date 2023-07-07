from pydantic import BaseModel


class User(BaseModel):
    """A MAAS user."""

    id: int
    username: str
    email: str
