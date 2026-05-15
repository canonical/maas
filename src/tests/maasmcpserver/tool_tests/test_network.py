# Copyright 2026 Canonical Ltd.  This software is licensed under the GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from maasmcpserver.config import MaasServerConfig
from maasmcpserver.errors import MAASPermissionError
from maasmcpserver.tools import network

FABRIC_PAYLOAD = {
    "id": 1,
    "name": "fabric-0",
    "class_type": None,
    "description": "default",
}

VLAN_PAYLOAD = {
    "id": 5001,
    "vid": 0,
    "name": "untagged",
    "mtu": 1500,
    "dhcp_on": True,
    "fabric": {"id": 1},
}

SUBNET_PAYLOAD = {
    "id": 1,
    "name": "192.168.1.0/24",
    "cidr": "192.168.1.0/24",
    "gateway_ip": "192.168.1.1",
    "dns_servers": [],
    "vlan": {"id": 5001},
    "fabric": {"id": 1},
}


def make_response(data: object, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.json.return_value = data
    response.status_code = status_code
    response.text = str(data)
    return response


def make_http_error(
    status_code: int,
    detail: str,
) -> httpx.HTTPStatusError:
    response = MagicMock()
    response.status_code = status_code
    response.text = detail
    response.json.return_value = {"detail": detail}
    return httpx.HTTPStatusError(
        detail,
        request=MagicMock(),
        response=response,
    )


@pytest.fixture(autouse=True)
def set_maas_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAAS_URL", "http://maas.example.com")


@pytest.fixture(autouse=True)
def mock_context() -> Iterator[tuple[MagicMock, MagicMock]]:
    with (
        patch(
            "maasmcpserver.middleware.get_api_key",
            return_value="test-api-key",
        ),
        patch(
            "maasmcpserver.middleware.get_session_id",
            return_value="test-session-id",
        ),
        patch(
            "maasmcpserver.tools.network.get_api_key",
            return_value="test-api-key",
        ),
        patch(
            "maasmcpserver.tools.network.get_session_id",
            return_value="test-session-id",
        ),
        patch(
            "maasmcpserver.tools.network.log_tool_received"
        ) as log_tool_received,
        patch(
            "maasmcpserver.tools.network.log_tool_outcome"
        ) as log_tool_outcome,
    ):
        yield log_tool_received, log_tool_outcome


@pytest.fixture
def config() -> MaasServerConfig:
    return MaasServerConfig(maas_url="http://maas.example.com")


@pytest.fixture
def registered_tools(
    config: MaasServerConfig,
) -> dict[str, Callable[..., object]]:
    registered: dict[str, Callable[..., object]] = {}

    class FakeMCP:
        def tool(
            self,
            **_: object,
        ) -> Callable[[Callable[..., object]], Callable[..., object]]:
            def decorator(
                func: Callable[..., object],
            ) -> Callable[..., object]:
                registered[func.__name__] = func
                return func

            return decorator

        def resource(
            self,
            _uri: str,
            **_kwargs: object,
        ) -> Callable[[Callable[..., object]], Callable[..., object]]:
            def decorator(
                func: Callable[..., object],
            ) -> Callable[..., object]:
                registered[func.__name__] = func
                return func

            return decorator

    network.register(FakeMCP(), config)
    return registered


@pytest.fixture
def mock_maas_client() -> Iterator[tuple[MagicMock, MagicMock]]:
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    client.client = MagicMock()
    client.client.aclose = AsyncMock()

    with patch(
        "maasmcpserver.tools.network.MAASClient",
        return_value=client,
    ) as client_class:
        yield client_class, client


@pytest.mark.asyncio
async def test_list_subnets_requires_fabric_and_vlan_ids(
    registered_tools: dict[str, Callable[..., object]],
) -> None:
    with pytest.raises(TypeError):
        registered_tools["list_subnets"]()


@pytest.mark.asyncio
async def test_create_subnet_posts_to_nested_subnets_path(
    config: MaasServerConfig,
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    client_class, client = mock_maas_client
    client.post.return_value = make_response(SUBNET_PAYLOAD)

    result = await registered_tools["create_subnet"](
        fabric_id=1,
        vlan_id=5001,
        cidr="192.168.1.0/24",
        name="192.168.1.0/24",
        gateway_ip="192.168.1.1",
        dns_servers=["8.8.8.8"],
    )

    client_class.assert_called_once_with(config, "test-api-key")
    client.post.assert_awaited_once_with(
        "/MAAS/a/v3/fabrics/{fabric_id}/vlans/{vlan_id}/subnets",
        path_params={"fabric_id": 1, "vlan_id": 5001},
        body={
            "cidr": "192.168.1.0/24",
            "name": "192.168.1.0/24",
            "gateway_ip": "192.168.1.1",
            "dns_servers": ["8.8.8.8"],
        },
    )
    assert client.post.await_args.args[0] != "/MAAS/a/v3/subnets"
    assert "Subnet created: CIDR=192.168.1.0/24" in result
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_fabric_success_includes_fabric_name(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(FABRIC_PAYLOAD)
    client.delete.return_value = make_response({}, status_code=204)

    result = await registered_tools["delete_fabric"](fabric_id=1)

    assert result == "Fabric deleted: ID=1, Name=fabric-0"
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_vlan_success_includes_vid_and_name(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(VLAN_PAYLOAD)
    client.delete.return_value = make_response({}, status_code=204)

    result = await registered_tools["delete_vlan"](fabric_id=1, vlan_id=5001)

    assert result == "VLAN deleted: VID=0, Name=untagged, ID=5001"
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_subnet_success_includes_context(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(SUBNET_PAYLOAD)
    client.delete.return_value = make_response({}, status_code=204)

    result = await registered_tools["delete_subnet"](
        fabric_id=1,
        vlan_id=5001,
        subnet_id=1,
    )

    assert result == (
        "Subnet deleted: CIDR=192.168.1.0/24, Name=192.168.1.0/24, "
        "ID=1 (Fabric 1, VLAN 5001)"
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_fabric_returns_descriptive_404_error(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.side_effect = make_http_error(404, "Not found")

    result = await registered_tools["get_fabric"](fabric_id=1)

    assert result == 'Error (error_code: "http_error"): HTTP 404: Not found'
    client.get.assert_awaited_once()
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_vlan_returns_descriptive_404_error(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(VLAN_PAYLOAD)
    client.delete.side_effect = make_http_error(
        404,
        "Not found",
    )

    result = await registered_tools["delete_vlan"](fabric_id=1, vlan_id=5001)

    assert result == (
        'Error (error_code: "not_found"): VLAN ID=5001 was not '
        "found in fabric 1."
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_permission_error_is_returned_without_retry(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
    mock_context: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    _, log_tool_outcome = mock_context
    client.post.side_effect = MAASPermissionError(403)

    result = await registered_tools["create_fabric"](name="fabric-1")

    assert (
        result
        == 'Error (error_code: "permission_denied"): Permission denied (HTTP 403).'
    )
    assert client.post.await_count == 1
    log_tool_outcome.assert_called_once_with(
        "test-session-id",
        "create_fabric",
        "error",
        "permission_denied",
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_fabrics_returns_table(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(
        {"items": [FABRIC_PAYLOAD, {"id": 2, "name": "fabric-1", "class_type": None, "description": ""}]}
    )

    result = await registered_tools["list_fabrics"]()

    client.get.assert_awaited_once_with("/MAAS/a/v3/fabrics")
    assert "fabric-0" in result
    assert "fabric-1" in result
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_fabrics_returns_message_when_empty(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response({"items": []})

    result = await registered_tools["list_fabrics"]()

    assert result == "No fabrics found."
    client.client.aclose.assert_awaited_once()
