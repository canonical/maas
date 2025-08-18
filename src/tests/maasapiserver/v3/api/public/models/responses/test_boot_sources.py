# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64

from maasapiserver.v3.api.public.models.responses.boot_sources import (
    BootSourceResponse,
    SourceAvailableImageResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.bootsources import (
    BootSource,
    SourceAvailableImage,
)
from maasservicelayer.utils.date import utcnow


class TestBootSourceResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        data = base64.b64encode("data".encode("utf-8"))
        boot_source = BootSource(
            id=1,
            created=now,
            updated=now,
            url="my-url",
            keyring_filename="keyring-filename",
            keyring_data=data,
            priority=10,
            skip_keyring_verification=False,
        )
        bootsource_response = BootSourceResponse.from_model(
            boot_source=boot_source,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources",
        )
        assert boot_source.id == bootsource_response.id
        assert boot_source.url == bootsource_response.url
        assert (
            boot_source.keyring_filename
            == bootsource_response.keyring_filename
        )
        assert (
            boot_source.keyring_data.decode("utf-8")
            == bootsource_response.keyring_data
        )
        assert boot_source.priority == bootsource_response.priority
        assert (
            boot_source.skip_keyring_verification
            == bootsource_response.skip_keyring_verification
        )


class TestSourceAvailableImageResponse:
    def test_from_model(self) -> None:
        image = SourceAvailableImage(
            os="ubuntu",
            release="noble",
            release_title="24.04 LTS",
            architecture="amd64",
        )
        image_response = SourceAvailableImageResponse.from_model(image)

        assert image_response.kind == "SourceAvailableImage"
        assert image_response.os == image.os
        assert image_response.release == image.release
        assert image_response.release_title == image.release_title
        assert image_response.architecture == image.architecture
