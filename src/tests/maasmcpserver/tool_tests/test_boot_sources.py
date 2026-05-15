# Copyright 2026 Canonical Ltd.  This software is licensed under the GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from maasmcpserver.config import MaasServerConfig
from maasmcpserver.tools import boot_sources, deferred_tool, DEFERRED_TOOLS

BOOT_SOURCES_PAYLOAD = {
    "items": [
        {
            "id": 1,
            "url": "http://images.maas.io/ephemeral-v3/stable/",
            "keyring_data": None,
            "selections": [
                {
                    "id": 1,
                    "os": "ubuntu",
                    "release": "focal",
                    "arches": ["amd64"],
                    "subarches": ["*"],
                    "labels": ["*"],
                }
            ],
        }
    ]
}

BOOT_SOURCE_PAYLOAD = {
    "id": 1,
    "url": "http://images.maas.io/ephemeral-v3/stable/",
    "keyring_data": None,
    "selections": [],
}


SELECTIONS_PAYLOAD = {
    "items": [
        {
            "id": 1,
            "os": "ubuntu",
            "release": "noble",
            "architecture": "amd64",
            "title": "Ubuntu 24.04 LTS",
            "boot_source_id": 1,
        },
        {
            "id": 2,
            "os": "ubuntu",
            "release": "jammy",
            "architecture": "arm64",
            "title": "Ubuntu 22.04 LTS",
            "boot_source_id": 1,
        },
    ]
}

AVAILABLE_IMAGES_PAYLOAD = {
    "items": [
        {
            "os": "ubuntu",
            "release": "noble",
            "architecture": "amd64",
            "title": "Ubuntu 24.04 LTS",
            "source_id": 1,
            "source_url": "http://images.maas.io/ephemeral-v3/stable/",
        },
    ]
}

CUSTOM_IMAGES_PAYLOAD = {
    "items": [
        {
            "id": 10,
            "os": "custom",
            "release": "myimage",
            "architecture": "amd64",
            "sub_architecture": "generic",
        },
    ]
}


def make_response(data: object, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.json.return_value = data
    response.status_code = status_code
    response.text = str(data)
    response.content = b"payload"
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
            "maasmcpserver.tools.boot_sources.get_api_key",
            return_value="test-api-key",
        ),
        patch(
            "maasmcpserver.tools.boot_sources.get_session_id",
            return_value="test-session-id",
        ),
        patch(
            "maasmcpserver.tools.boot_sources.log_tool_received"
        ) as log_tool_received,
        patch(
            "maasmcpserver.tools.boot_sources.log_tool_outcome"
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

    boot_sources.register(FakeMCP(), config)
    return registered


@pytest.fixture
def mock_maas_client() -> Iterator[tuple[MagicMock, MagicMock]]:
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.delete = AsyncMock()
    client.client = MagicMock()
    client.client.aclose = AsyncMock()

    with patch(
        "maasmcpserver.tools.boot_sources.MAASClient",
        return_value=client,
    ) as client_class:
        yield client_class, client


@pytest.mark.asyncio
async def test_list_boot_sources_formats_sources_and_selections(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(BOOT_SOURCES_PAYLOAD)

    result = await registered_tools["list_boot_sources"]()

    client.get.assert_awaited_once_with("/MAAS/a/v3/boot_sources")
    assert "## Boot Sources" in result
    assert "### Source 1 (ID: 1)" in result
    assert "URL: http://images.maas.io/ephemeral-v3/stable/" in result
    assert "Keyring: None" in result
    assert (
        "- OS: ubuntu, Release: focal, Arches: [amd64], Labels: [*]" in result
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_boot_source_sync_posts_to_sync_path_with_only_ids(
    config: MaasServerConfig,
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    client_class, client = mock_maas_client
    client.post.return_value = make_response({}, status_code=202)

    result = await registered_tools["trigger_boot_source_sync"](
        boot_source_id=1,
        selection_id=7,
    )

    client_class.assert_called_once_with(config, "test-api-key")
    client.post.assert_awaited_once_with(
        "/MAAS/a/v3/boot_sources/{boot_source_id}/selections/"
        "{selection_id}:sync",
        path_params={"boot_source_id": 1, "selection_id": 7},
    )
    assert client.post.await_args.args[0].endswith(":sync")
    assert "body" not in client.post.await_args.kwargs
    assert "query_params" not in client.post.await_args.kwargs
    assert "Boot source sync triggered." in result
    assert "Boot Source ID: 1" in result
    assert "Selection ID: 7" in result

    with pytest.raises(TypeError):
        await registered_tools["trigger_boot_source_sync"](
            boot_source_id=1,
            selection_id=7,
            url="http://images.maas.io/",
        )

    assert client.post.await_count == 1
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_boot_source_success_includes_source_id_and_url(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(BOOT_SOURCE_PAYLOAD)
    client.delete.return_value = make_response({}, status_code=204)

    result = await registered_tools["delete_boot_source"](boot_source_id=1)

    client.get.assert_awaited_once_with(
        "/MAAS/a/v3/boot_sources/{boot_source_id}",
        path_params={"boot_source_id": 1},
    )
    client.delete.assert_awaited_once_with(
        "/MAAS/a/v3/boot_sources/{boot_source_id}",
        path_params={"boot_source_id": 1},
    )
    assert result == (
        "Boot source deleted: ID=1, "
        "URL=http://images.maas.io/ephemeral-v3/stable/"
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_boot_source_returns_descriptive_not_found_error(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.side_effect = make_http_error(404, "Not found")

    result = await registered_tools["delete_boot_source"](boot_source_id=1)

    assert result == (
        'Error (error_code: "not_found"): Boot source 1 was not found.'
    )
    client.delete.assert_not_called()
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_deferred_tool_guard_returns_tc2_error_without_api_calls() -> (
    None
):
    assert "deploy" in DEFERRED_TOOLS

    with patch("maasmcpserver.tools.boot_sources.MAASClient") as client_class:

        @deferred_tool("deploy")
        async def deploy_machine() -> None:
            return None

        result = await deploy_machine()

    assert result["type"] == "not-implemented"
    assert "TC-2" in result["error"]
    assert "deploy" in result["error"]
    client_class.assert_not_called()


@pytest.mark.asyncio
async def test_list_boot_source_selections_returns_formatted_list(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(SELECTIONS_PAYLOAD)

    result = await registered_tools["list_boot_source_selections"](
        boot_source_id=1
    )

    client.get.assert_awaited_once_with(
        "/MAAS/a/v3/boot_sources/{boot_source_id}/selections",
        path_params={"boot_source_id": 1},
        query_params={"page": 1, "size": 100},
    )
    assert "Selections for Boot Source 1" in result
    assert "OS: ubuntu" in result
    assert "Release: noble" in result
    assert "Arch: amd64" in result


@pytest.mark.asyncio
async def test_list_available_images_returns_formatted_list(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(AVAILABLE_IMAGES_PAYLOAD)

    result = await registered_tools["list_available_images"]()

    client.get.assert_awaited_once_with("/MAAS/a/v3/available_images")
    assert "## Available Images" in result
    assert "OS: ubuntu" in result
    assert "Release: noble" in result
    assert "Source ID: 1" in result
    assert "Source URL: http://images.maas.io" in result
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_available_images_returns_empty_message_when_none(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response({"items": []})

    result = await registered_tools["list_available_images"]()

    assert "No available images found." in result
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_selections_returns_list(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(SELECTIONS_PAYLOAD)

    result = await registered_tools["list_selections"]()

    client.get.assert_awaited_once_with("/MAAS/a/v3/selections")
    assert "## Image Selections" in result
    assert "OS: ubuntu" in result
    assert "Release: noble" in result
    assert "Release: jammy" in result
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_custom_images_returns_formatted_list(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(CUSTOM_IMAGES_PAYLOAD)

    result = await registered_tools["list_custom_images"]()

    client.get.assert_awaited_once_with(
        "/MAAS/a/v3/custom_images",
        query_params={"page": 1, "size": 100},
    )
    assert "## Custom Images" in result
    assert "ID: 10" in result
    assert "OS: custom" in result
    assert "Release: myimage" in result
    assert "Sub-arch: generic" in result


@pytest.mark.asyncio
async def test_list_custom_images_returns_empty_message_when_none(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response({"items": []})

    result = await registered_tools["list_custom_images"]()

    assert "No custom images found." in result
