from typing import Optional
from urllib.parse import quote_plus

from requests.models import Response
from requests.utils import add_dict_to_cookiejar
from requests_unixsocket import Session

from .settings import api_service_socket_path


class APIServerClient:
    def __init__(
        self,
        session_id: str,
        session: Optional[Session] = None,
        version: int = 2,
    ):
        self.session = session or Session()
        add_dict_to_cookiejar(self.session.cookies, {"sessionid": session_id})
        path = str(api_service_socket_path())
        self.socket_path = f"http+unix://{quote_plus(path)}"
        self.prefix = f"/api/v{version}/"

    def request(self, verb: str, path: str, **kwargs) -> Response:
        url = self.socket_path + self.prefix + path.lstrip("/")
        return self.session.request(verb, url, **kwargs)

    def get(self, path: str, **kwargs) -> Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Response:
        return self.request("DELETE", path, **kwargs)
