import pytest
from requests.utils import dict_from_cookiejar

from maasapiserver.client import APIServerClient

SAMPLE_SESSION_ID = "abcdef"


@pytest.fixture
def client(mocker):
    client = APIServerClient(SAMPLE_SESSION_ID)
    mocker.patch.object(client.session, "request")
    # override the socket path to a known value
    client.socket_path = "http+unix://socket"
    yield client


class TestAPIServerClient:
    def test_session_cookie(self, client):
        assert dict_from_cookiejar(client.session.cookies) == {
            "sessionid": SAMPLE_SESSION_ID
        }

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("endpoint", "http+unix://socket/api/v1/endpoint"),
            ("/endpoint", "http+unix://socket/api/v1/endpoint"),
            ("/some/path", "http+unix://socket/api/v1/some/path"),
        ],
    )
    def test_request(self, client, path, expected):
        client.request("GET", path)
        client.session.request.assert_called_with("GET", expected)

    def test_get(self, client):
        client.get("endpoint")
        client.session.request.assert_called_with(
            "GET", "http+unix://socket/api/v1/endpoint"
        )

    def test_post(self, client):
        kwargs = {
            "json": {"key": "value"},
        }
        client.post("endpoint", **kwargs)
        client.session.request.assert_called_with(
            "POST", "http+unix://socket/api/v1/endpoint", **kwargs
        )

    def test_put(self, client):
        kwargs = {
            "json": {"key": "value"},
        }
        client.put("endpoint", **kwargs)
        client.session.request.assert_called_with(
            "PUT", "http+unix://socket/api/v1/endpoint", **kwargs
        )

    def test_delete(self, client):
        client.delete("endpoint")
        client.session.request.assert_called_with(
            "DELETE",
            "http+unix://socket/api/v1/endpoint",
        )
