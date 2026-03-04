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

from abc import ABCMeta, abstractmethod
from datetime import date, datetime
from enum import StrEnum
from typing import Generic, override, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    ValidationError,
)

VersionT = TypeVar("VersionT", bound="Version")


def updated_validator(v: str | datetime) -> datetime:
    if isinstance(v, datetime):
        return v
    try:
        return datetime.strptime(v, "%a, %d %b %Y %H:%M:%S %z")
    except ValueError:
        # when serializing the object, the date will be in ISO format.
        return datetime.fromisoformat(v)


def support_eol_validator(v: str | None) -> date | None:
    if v is not None and not isinstance(v, date):
        try:
            # date is a string in the format YYYY-MM-DD
            year, month, day = [int(value) for value in v.split("-")]
            return date(year, month, day)
        except ValueError:
            # when serializing the object, the date will be in ISO format.
            return date.fromisoformat(v)
    return v


class Datatype(StrEnum):
    image_ids = "image-ids"
    image_downloads = "image-downloads"


class IndexContent(BaseModel):
    name: str
    path: str
    updated: datetime
    datatype: Datatype | None = None
    format: str = "products:1.0"
    products: list[str]

    @field_validator("updated", mode="before")
    @classmethod
    def validate_updated(cls, v: str | datetime) -> datetime:
        return updated_validator(v)


class SimpleStreamsIndexList(BaseModel):
    updated: datetime
    format: str = "index:1.0"
    indexes: list[IndexContent]

    @field_validator("updated", mode="before")
    @classmethod
    def validate_updated(cls, v: str | datetime) -> datetime:
        return updated_validator(v)

    @model_validator(mode="before")
    @classmethod
    def preprocess_index(cls, v: dict) -> dict:
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
    kpackage: str | None = None


class Version(BaseModel, metaclass=ABCMeta):
    model_config = ConfigDict(validate_by_alias=True, serialize_by_alias=True)

    version_name: str

    @model_validator(mode="before")
    @classmethod
    def preprocess_items(cls, v: dict) -> dict:
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
    grub2_signed: BootloaderFile | None = Field(
        None,
        alias="grub2-signed",
    )
    shim_signed: BootloaderFile | None = Field(None, alias="shim-signed")
    grub2: BootloaderFile | None = None
    syslinux: BootloaderFile | None = None

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
    support_eol: date | None = None
    support_esm_eol: date | None = None
    boot_initrd: ImageFile = Field(..., alias="boot-initrd")
    boot_kernel: ImageFile = Field(..., alias="boot-kernel")
    manifest: ImageFile
    root_image_gz: ImageFile | None = Field(
        None,
        alias="root-image.gz",
    )
    squashfs: ImageFile | None = None

    @field_validator("support_eol", "support_esm_eol", mode="before")
    @classmethod
    def validate_support_eol(cls, v: str | None) -> date | None:
        return support_eol_validator(v)

    @override
    def get_downloadable_files(self) -> list[DownloadableFile]:
        files = [
            self.boot_initrd,
            self.boot_kernel,
            self.squashfs,
            self.root_image_gz,
        ]
        return [file for file in files if file is not None]


class SingleFileImageVersion(Version):
    manifest: ImageFile
    root_tgz: ImageFile = Field(..., alias="root-tgz")

    @override
    def get_downloadable_files(self) -> list[DownloadableFile]:
        return [self.root_tgz]


class Product(BaseModel, Generic[VersionT], metaclass=ABCMeta):
    model_config = ConfigDict(validate_by_alias=True, serialize_by_alias=True)

    product_name: str
    arch: str
    label: str
    os: str
    versions: list[VersionT]

    @staticmethod
    @abstractmethod
    def version_class() -> type[Version]:
        """Return the Version subclass for this Product type.

        Required by preprocess_versions validator to instantiate correct
        version objects during deserialization. Concrete subclasses must
        implement this to specify their supported version type.
        """
        pass

    @model_validator(mode="before")
    @classmethod
    def preprocess_versions(cls, v: dict) -> dict:
        """Transform versions in a list.

        The 'versions' field is a dict where the key is the version name and the
        value is a version object, like:
            {"20250301": {"items": {"squashfs": {...}, ...}, ...}}
        """

        # When serializing the object as a dict and then re-converting it into a
        # model we might not need to to the pre-processing.
        if (
            isinstance(v, dict)
            and v.get("versions")
            and isinstance(v["versions"], dict)
        ):
            versions = []
            for prod_name, version in v["versions"].items():
                versions.append(
                    cls.version_class()(version_name=prod_name, **version)
                )
            v["versions"] = versions
        return v

    def get_latest_version(self) -> VersionT:
        # we are usually interested only in the last version
        return sorted(self.versions, key=lambda v: v.version_name)[-1]

    def get_version_by_name(self, name: str) -> VersionT | None:
        for v in self.versions:
            if v.version_name == name:
                return v
        return None


class BootloaderProduct(Product[BootloaderVersion]):
    arches: str
    bootloader_type: str = Field(
        ...,
        alias="bootloader-type",
    )

    @override
    @staticmethod
    def version_class() -> type[Version]:
        return BootloaderVersion

    def __hash__(self) -> int:
        return hash((self.os, self.arch, self.bootloader_type))


class ImageProduct(Product[VersionT], metaclass=ABCMeta):
    release: str
    release_title: str
    subarch: str
    subarches: str
    support_eol: date | None
    version: str

    @field_validator("support_eol", mode="before")
    @classmethod
    def validate_support_eol(cls, v: str | None) -> date | None:
        return support_eol_validator(v)

    def __hash__(self) -> int:
        return hash((self.os, self.release, self.arch, self.subarch))


class MultiFileProduct(ImageProduct[MultiFileImageVersion]):
    kflavor: str
    krel: str  # seems to not be used
    release_codename: str

    @override
    @staticmethod
    def version_class() -> type[Version]:
        return MultiFileImageVersion


class SingleFileProduct(ImageProduct[SingleFileImageVersion]):
    @override
    @staticmethod
    def version_class() -> type[Version]:
        return SingleFileImageVersion


class SimpleStreamsProductList(BaseModel, metaclass=ABCMeta):
    model_config = ConfigDict(validate_by_alias=True, serialize_by_alias=True)

    content_id: str
    datatype: Datatype
    format: str = "products:1.0"
    updated: datetime
    products: list[Product]

    @field_validator("updated", mode="before")
    @classmethod
    def validate_updated(cls, v: str | datetime) -> datetime:
        return updated_validator(v)

    @staticmethod
    @abstractmethod
    def product_class() -> type[Product]:
        pass

    @model_validator(mode="before")
    @classmethod
    def preprocess_products(cls, v: dict) -> dict:
        """Transform products into a list of product objects.
        'products' is a dict like
        {"com.ubuntu.maas.stable:v3:boot:12.04:amd64:hwe-p": {<product>}}
        """

        # When serializing the object as a dict and then re-converting it into a
        # model we might not need to do the pre-processing.
        if (
            isinstance(v, dict)
            and v.get("products")
            and isinstance(v["products"], dict)
        ):
            products = []
            for product_name, product in v["products"].items():
                product = cls.product_class()(
                    product_name=product_name, **product
                )
                products.append(product)
            v["products"] = products
        return v


class SimpleStreamsBootloaderProductList(SimpleStreamsProductList):
    @override
    @staticmethod
    def product_class() -> type[Product]:
        return BootloaderProduct


class SimpleStreamsMultiFileProductList(SimpleStreamsProductList):
    @override
    @staticmethod
    def product_class() -> type[Product]:
        return MultiFileProduct


class SimpleStreamsSingleFileProductList(SimpleStreamsProductList):
    @override
    @staticmethod
    def product_class() -> type[Product]:
        return SingleFileProduct


# Union type for concrete SimpleStreams product list types
SimpleStreamsProductListType = (
    SimpleStreamsBootloaderProductList
    | SimpleStreamsSingleFileProductList
    | SimpleStreamsMultiFileProductList
)

# Define a manifest as a list of SimpleStreams product lists
SimpleStreamsManifest = list[SimpleStreamsProductListType]


class SimpleStreamsProductListFactory:
    @staticmethod
    def produce(data: dict) -> SimpleStreamsProductListType:
        product: SimpleStreamsProductListType | None = None
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
