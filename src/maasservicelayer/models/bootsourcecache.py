# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import date

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class BootSourceCache(MaasTimestampedBaseModel):
    os: str
    arch: str
    subarch: str
    release: str
    label: str
    boot_source_id: int
    release_codename: str | None = None
    release_title: str | None = None
    support_eol: date | None = None
    kflavor: str | None = None
    bootloader_type: str | None = None
    extra: dict
    latest_version: str | None = None
