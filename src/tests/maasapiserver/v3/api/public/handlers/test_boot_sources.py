# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode, b64encode
from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.requests.boot_sources import (
    BootSourceFetchRequest,
)
from maasapiserver.v3.api.public.models.responses.boot_sources import (
    BootSourceFetchListResponse,
    BootSourceFetchResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.utils.images.boot_image_mapping import BootImageMapping
from maasservicelayer.utils.images.helpers import ImageSpec
from tests.fixtures.factories.boot_sources import set_resource
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

IMAGE_DESC_1 = {
    "content_id": "com.ubuntu.maas:stable:v3:download",
    "product_name": "com.ubuntu.maas.stable:v3:boot:16.04:s390x:ga-16.04",
    "version_name": "20210928",
    "path": "xenial/s390x/20210928/ga-16.04/generic/boot-initrd",
    "subarches": "generic,hwe-p,hwe-q,hwe-r,hwe-s,hwe-t,hwe-u,hwe-v,hwe-w,ga-16.04",
    "release_codename": "Xenial Xerus",
    "release_title": "16.04 LTS",
    "support_eol": "2021-04-21",
    "kflavor": "generic",
}
IMAGE_DESC_2 = {
    "content_id": "com.ubuntu.maas:stable:v3:download",
    "product_name": "com.ubuntu.maas.stable:v3:boot:24.10:s390x:ga-24.10",
    "version_name": "20250430",
    "path": "oracular/s390x/20250430/ga-24.10/generic/boot-initrd",
    "subarches": "generic,hwe-p,hwe-q,hwe-r,hwe-s,hwe-t,hwe-u,hwe-v,hwe-w,ga-16.04,ga-16.10,ga-17.04,ga-17.10,ga-18.04,ga-18.10,ga-19.04,ga-19.10,ga-20.04,ga-20.10,ga-21.04,ga-21.10,ga-22.04,ga-22.10,ga-23.04,ga-23.10,ga-24.04,ga-24.10",
    "release_codename": "Oracular Oriole",
    "release_title": "24.10",
    "support_eol": "2025-07-10",
    "kflavor": "generic",
}
IMAGE_DESC_3 = {
    "content_id": "com.ubuntu.maas:stable:v3:download",
    "product_name": "com.ubuntu.maas.stable:v3:boot:24.04:s390x:ga-24.04",
    "version_name": "20250424",
    "path": "noble/s390x/20250424/ga-24.04/generic/boot-initrd",
    "subarches": "generic,hwe-p,hwe-q,hwe-r,hwe-s,hwe-t,hwe-u,hwe-v,hwe-w,ga-16.04,ga-16.10,ga-17.04,ga-17.10,ga-18.04,ga-18.10,ga-19.04,ga-19.10,ga-20.04,ga-20.10,ga-21.04,ga-21.10,ga-22.04,ga-22.10,ga-23.04,ga-23.10,ga-24.04",
    "release_codename": "Noble Numbat",
    "release_title": "24.04 LTS",
    "support_eol": "2029-05-31",
    "kflavor": "generic",
}


class TestBootSourcesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/boot_sources"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}:fetch"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_fetch_boot_sources(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        # Construct a BootImageMapping with some fake image specs.
        mapping = BootImageMapping()

        image_specs = [
            ImageSpec(
                os="ubuntu",
                arch="s390x",
                subarch="hwe-w",
                kflavor="generic",
                release="xenial",
                label="stable",
            ),
            ImageSpec(
                os="ubuntu",
                arch="s390x",
                subarch="hwe-w",
                kflavor="generic",
                release="oracular",
                label="stable",
            ),
            ImageSpec(
                os="ubuntu",
                arch="s390x",
                subarch="hwe-w",
                kflavor="generic",
                release="noble",
                label="stable",
            ),
        ]
        descriptions = [
            IMAGE_DESC_1,
            IMAGE_DESC_2,
            IMAGE_DESC_3,
        ]
        for spec, desc in zip(image_specs, descriptions):
            set_resource(mapping, spec, desc)

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.fetch.return_value = mapping

        request = BootSourceFetchRequest(
            url="https://path/to/images/server",
        )

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}:fetch", json=jsonable_encoder(request)
        )

        assert response.status_code == 200

        actual_response = BootSourceFetchListResponse(**response.json())

        expected_items = [
            BootSourceFetchResponse.from_model((spec, desc))
            for spec, desc in zip(image_specs, descriptions)
        ]

        for resp in actual_response.items:
            assert resp in expected_items

    async def test_fetch_encodes_keyring_data(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        images_server_url = "https://path/to/images/server"
        keyring_data_str = b64encode(b"keyring_data")

        expected_bytes = b64decode(keyring_data_str)

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.fetch.return_value = BootImageMapping()

        request = BootSourceFetchRequest(
            url=images_server_url,
            keyring_data=keyring_data_str,
        )

        response = await mocked_api_client_user.post(
            url=f"{self.BASE_PATH}:fetch",
            json=jsonable_encoder(request),
        )

        assert response.status_code == 200

        services_mock.boot_sources.fetch.assert_called_once_with(
            images_server_url,
            keyring_path=None,
            keyring_data=expected_bytes,
            validate_products=True,
        )
