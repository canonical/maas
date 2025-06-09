from fastapi.security import OAuth2PasswordBearer
from starlette.requests import Request


class OpenapiOAuth2PasswordBearer(OAuth2PasswordBearer):
    def __init__(self, tokenUrl=str):
        super().__init__(tokenUrl, scheme_name="OAuth2PasswordBearer")  # pyright: ignore [reportArgumentType]

    async def __call__(self, request: Request) -> None:
        """Do nothing, this is just a hack to generate the openapi spec with the security schema."""
        return None
