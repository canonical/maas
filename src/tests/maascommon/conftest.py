# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path

from aiohttp import web
import pytest

from maascommon.enums.openfga import OPENFGA_STORE_ID
from maascommon.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
    OperatingSystemRegistry,
)
from maascommon.utils.registry import _registry
from maastesting.factory import factory


class FakeOS(OperatingSystem):
    name = ""
    title = ""

    def __init__(self, name, purpose=None, releases=None):
        self.name = name
        self.title = name
        self.purpose = purpose
        if releases is None:
            self.fake_list = [factory.make_string() for _ in range(3)]
        else:
            self.fake_list = releases

    def get_boot_image_purposes(self, *args):
        if self.purpose is None:
            return [BOOT_IMAGE_PURPOSE.XINSTALL]
        else:
            return self.purpose

    def get_supported_releases(self):
        return self.fake_list

    def get_default_release(self):
        return self.fake_list[0]

    def get_release_title(self, release):
        return release


@pytest.fixture
def temporary_os():
    osystem = factory.make_name("os")
    purpose = [
        BOOT_IMAGE_PURPOSE.COMMISSIONING,
        BOOT_IMAGE_PURPOSE.INSTALL,
        BOOT_IMAGE_PURPOSE.XINSTALL,
    ]
    fake = FakeOS(osystem, purpose)
    OperatingSystemRegistry.register_item(fake.name, fake)
    yield fake
    OperatingSystemRegistry.unregister_item(osystem)


@pytest.fixture
def osystem_registry():
    registry_copy = _registry.copy()
    _registry.clear()
    yield
    _registry.clear()
    _registry.update(registry_copy)


class StubOpenFGAServer:
    def __init__(self):
        self.allowed = True
        self.last_payload = None
        self.status_code = 200
        self.list_objects_response = {"objects": []}

    async def check_handler(self, request):
        self.last_payload = await request.json()
        if self.status_code != 200:
            return web.Response(status=self.status_code)
        return web.json_response({"allowed": self.allowed, "resolution": ""})

    async def list_objects_handler(self, request):
        self.last_payload = await request.json()
        if self.status_code != 200:
            return web.Response(status=self.status_code)
        return web.json_response(self.list_objects_response)


@pytest.fixture
async def stub_openfga_server(tmp_path: Path):
    socket_path = str(tmp_path / "test-openfga.sock")
    handler_store = StubOpenFGAServer()

    app = web.Application()
    app.router.add_post(
        f"/stores/{OPENFGA_STORE_ID}/check", handler_store.check_handler
    )
    app.router.add_post(
        f"/stores/{OPENFGA_STORE_ID}/list-objects",
        handler_store.list_objects_handler,
    )

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.UnixSite(runner, socket_path)
    await site.start()

    yield handler_store, socket_path

    await runner.cleanup()
