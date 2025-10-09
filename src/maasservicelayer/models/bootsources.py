# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import dataclasses
from typing import Optional

from pydantic import BaseModel

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)
from maasservicelayer.simplestreams.models import (
    BootloaderProduct,
    ImageProduct,
    Product,
)


@generate_builder()
class BootSource(MaasTimestampedBaseModel):
    url: str
    keyring_filename: Optional[str]
    keyring_data: Optional[bytes]
    priority: int
    skip_keyring_verification: bool

    def __hash__(self):
        return hash(self.url)


class SourceAvailableImage(BaseModel):
    os: str
    release: str
    release_title: str
    architecture: str

    @classmethod
    def from_simplestreams_product(cls, product: Product):
        if isinstance(product, BootloaderProduct):
            release = product.bootloader_type
            release_title = product.bootloader_type
        elif isinstance(product, ImageProduct):
            release = product.release
            release_title = product.release_title
        else:
            raise ValueError(f"Unknown simplestreams product: {product}")

        return cls(
            os=product.os,
            release=release,
            release_title=release_title,
            architecture=product.arch,
        )


@dataclasses.dataclass
class BootSourceAvailableImage:
    os: str
    release: str
    release_title: str
    arch: str
    boot_source_id: int


@dataclasses.dataclass
class BootSourceCacheOSRelease:
    os: str
    release: str
