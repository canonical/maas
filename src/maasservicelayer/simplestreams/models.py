# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Simplestreams models.

This module defines the Pydantic models that represent SimpleStreams metadata.

The response from /streams/v1/index.json is mapped as a `SimpleStreamsIndexList`.

Individual product entries from the index are represented as subclasses of
`SimpleStreamsProductList`, including:

- `SimpleStreamsBootloaderProductList`
- `SimpleStreamsMultiFileProductList`
- `SimpleStreamsSingleFileProductList`


In this context, "SingleFile" and "MultiFile" refer to the image structure:
- SingleFile: An image composed solely of a root tarball.
- MultiFile: An image split into multiple components, such as a boot-initrd,
  boot-kernel, squashfs, and a root image.

Within MAAS' SimpleStreams mirror, these correspond to:
- CentOS images -> SingleFile
- Ubuntu images -> MultiFile

The naming is intentionally generic to avoid tightly coupling the classes to
specific distributions like Ubuntu or CentOS, because these model will match
other custom images as well.

The original structure of the SimpleStreams JSON has been slightly refactored
through the use of pydantic validators. See the preprocess_* validators.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import List, Optional, override, Type

from pydantic import (
    BaseModel,
    Field,
    root_validator,
    ValidationError,
    validator,
)


def updated_validator(v: str | None) -> datetime | None:
    if v is not None:
        return datetime.strptime(v, "%a, %d %b %Y %H:%M:%S %z")
    return v


def support_eol_validator(v: str | None) -> datetime | None:
    if v is not None:
        return datetime.strptime(v, "%Y-%m-%d")
    return v


class Datatype(Enum):
    image_ids = "image-ids"
    image_downloads = "image-downloads"


class IndexContent(BaseModel):
    name: str
    path: str
    updated: datetime | None
    datatype: Optional[Datatype]
    format: str = "products:1.0"
    products: List[str]

    # TODO: switch to field_validator when we migrate to pydantic 2.x
    _validate_updated = validator("updated", pre=True, allow_reuse=True)(
        updated_validator
    )


class SimpleStreamsIndexList(BaseModel):
    updated: datetime | None
    format: str = "index:1.0"
    indexes: list[IndexContent]

    # TODO: switch to field_validator when we migrate to pydantic 2.x
    _validate_updated = validator("updated", pre=True, allow_reuse=True)(
        updated_validator
    )

    @root_validator(pre=True)
    def preprocess_index(cls, v):
        """Transform 'index' into a list of IndexContent."""

        if v.get("index") and isinstance(v["index"], dict):
            indexes = []
            for name, index in v["index"].items():
                indexes.append(IndexContent(name=name, **index))
            del v["index"]
            v["indexes"] = indexes
        return v


class DownloadableFile(BaseModel):
    ftype: str
    path: str
    sha256: str
    size: int


class BootloaderFile(DownloadableFile):
    src_package: str
    src_release: str
    src_version: str


class ImageFile(DownloadableFile):
    kpackage: str | None


class Version(BaseModel, ABC):
    version_name: str

    @root_validator(pre=True)
    def preprocess_items(cls, v: dict):
        """Unpack items into the specific fields.

        A version is formed by a dict which has the following structure:
            {"items": {"boot-initrd": {...}, "boot-kernel": {...}, ...}
        This function unpacks the "items" content, directly in the object.
        """

        # When serializing the object as a dict and then re-converting it into a
        # model we might not need to do the pre-processing.
        if "items" in v:
            v.update(**v["items"])
            del v["items"]
        return v

    @abstractmethod
    def get_downloadable_files(
        self,
    ) -> list[DownloadableFile]:
        pass


class BootloaderVersion(Version):
    grub2_signed: BootloaderFile | None = Field(..., alias="grub2-signed")
    shim_signed: BootloaderFile | None = Field(..., alias="shim-signed")
    grub2: BootloaderFile | None
    syslinux: BootloaderFile | None

    @override
    def get_downloadable_files(self) -> list[DownloadableFile]:
        files = [
            self.grub2_signed,
            self.shim_signed,
            self.grub2,
            self.syslinux,
        ]
        return [file for file in files if file is not None]


class MultiFileImageVersion(Version):
    support_eol: datetime | None
    support_esm_eol: datetime | None
    boot_initrd: ImageFile = Field(..., alias="boot-initrd")
    boot_kernel: ImageFile = Field(..., alias="boot-kernel")
    manifest: ImageFile
    root_image_gz: ImageFile | None = Field(None, alias="root-image.gz")
    squashfs: ImageFile | None

    # TODO: switch to field_validator when we migrate to pydantic 2.x
    _validate_support_eol = validator(
        "support_eol", "support_esm_eol", pre=True, allow_reuse=True
    )(support_eol_validator)

    @override
    def get_downloadable_files(self) -> list[DownloadableFile]:
        files = [
            self.boot_initrd,
            self.boot_kernel,
            self.manifest,
            self.squashfs,
            self.root_image_gz,
        ]
        return [file for file in files if file is not None]


class SingleFileImageVersion(Version):
    manifest: ImageFile
    root_tgz: ImageFile = Field(..., alias="root-tgz")

    @override
    def get_downloadable_files(self) -> list[DownloadableFile]:
        return [self.manifest, self.root_tgz]


class Product(BaseModel, ABC):
    product_name: str
    arch: str
    label: str
    os: str
    versions: list

    @staticmethod
    @abstractmethod
    def version_class() -> Type[Version]:
        pass

    # TODO: switch to model_validator when we migrate to pydantic 2.x
    @root_validator(pre=True)
    def preprocess_versions(cls, v):
        """Transform versions in a list.

        The 'versions' field is a dict where the key is the version name and the
        value is a version object, like:
            {"20250301": {"items": {"squashfs": {...}, ...}, ...}}
        """

        # When serializing the object as a dict and then re-converting it into a
        # model we might not need to to the pre-processing.
        if v.get("versions") and isinstance(v["versions"], dict):
            versions = []
            for prod_name, version in v["versions"].items():
                versions.append(
                    cls.version_class()(version_name=prod_name, **version)
                )
            v["versions"] = versions
        return v

    def get_latest_version(self) -> Type[Version]:
        # we are usually interested only in the last version
        return sorted(self.versions, key=lambda v: v.version_name)[-1]

    def get_version_by_name(self, name: str) -> Version | None:
        for v in self.versions:
            if v.name == name:
                return v
        return None


class BootloaderProduct(Product):
    arches: str
    bootloader_type: str = Field(..., alias="bootloader-type")
    versions: list[BootloaderVersion]

    @override
    @staticmethod
    def version_class() -> Type[Version]:
        return BootloaderVersion


class ImageProduct(Product):
    release: str
    release_title: str
    subarch: str
    subarches: str
    support_eol: datetime | None
    version: str

    # TODO: switch to field_validator when we migrate to pydantic 2.x
    _validate_support_eol = validator(
        "support_eol", pre=True, allow_reuse=True
    )(support_eol_validator)


class MultiFileProduct(ImageProduct):
    kflavor: str
    krel: str  # seems to not be used
    release_codename: str
    versions: list[MultiFileImageVersion]

    @override
    @staticmethod
    def version_class() -> Type[Version]:
        return MultiFileImageVersion


class SingleFileProduct(ImageProduct):
    versions: list[SingleFileImageVersion]

    @override
    @staticmethod
    def version_class() -> Type[Version]:
        return SingleFileImageVersion


class SimpleStreamsProductList(BaseModel, ABC):
    content_id: str
    datatype: Datatype
    format: str = "products:1.0"
    updated: datetime | None
    products: list

    # TODO: switch to field_validator when we migrate to pydantic 2.x
    _validate_updated = validator("updated", pre=True, allow_reuse=True)(
        updated_validator
    )

    @staticmethod
    @abstractmethod
    def product_class() -> type[Product]:
        pass

    # TODO: switch to model_validator when we migrate to pydantic 2.x
    @root_validator(pre=True)
    def preprocess_products(cls, v: dict):
        """Transform products into a list of product objects.
        'products' is a dict like
        {"com.ubuntu.maas.stable:v3:boot:12.04:amd64:hwe-p": {<product>}}
        """

        # When serializing the object as a dict and then re-converting it into a
        # model we might not need to do the pre-processing.
        if v.get("products") and isinstance(v["products"], dict):
            products = []
            for product_name, product in v["products"].items():
                product = cls.product_class()(
                    product_name=product_name, **product
                )
                products.append(product)
            v["products"] = products
        return v


class SimpleStreamsBootloaderProductList(SimpleStreamsProductList):
    products: list[BootloaderProduct]

    @override
    @staticmethod
    def product_class() -> type[Product]:
        return BootloaderProduct


class SimpleStreamsMultiFileProductList(SimpleStreamsProductList):
    products: list[MultiFileProduct]

    @override
    @staticmethod
    def product_class() -> type[Product]:
        return MultiFileProduct


class SimpleStreamsSingleFileProductList(SimpleStreamsProductList):
    products: list[SingleFileProduct]

    @override
    @staticmethod
    def product_class() -> type[Product]:
        return SingleFileProduct


class SimpleStreamsProductListFactory:
    @staticmethod
    def produce(data) -> SimpleStreamsProductList:
        product = None
        try:
            product = SimpleStreamsBootloaderProductList(**data)
        except ValidationError:
            pass

        try:
            product = SimpleStreamsMultiFileProductList(**data)
        except ValidationError:
            pass

        try:
            product = SimpleStreamsSingleFileProductList(**data)
        except ValidationError:
            pass

        if product is None:
            raise ValueError(
                "Data does not match any known SimpleStreams model."
            )
        return product
