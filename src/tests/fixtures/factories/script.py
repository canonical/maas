# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta, timezone
from typing import Any

from maascommon.enums.node import HardwareDeviceTypeEnum
from maascommon.enums.script import ScriptParallel, ScriptType
from maasservicelayer.db.tables import ScriptTable, VersionedTextFileTable
from maasservicelayer.models.script import Script
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_versionedtextfile_entry(
    fixture: Fixture,
    **extra_details: Any,
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    versionedtextfile = {
        "created": created_at,
        "updated": updated_at,
        "data": "",
        "comment": None,
        "previous_version_id": None,
    }
    versionedtextfile.update(extra_details)

    [created_versionedtextfile] = await fixture.create(
        VersionedTextFileTable.name, versionedtextfile
    )
    return created_versionedtextfile


async def create_test_script_entry(
    fixture: Fixture,
    name: str,
    **extra_details: Any,
) -> Script:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    if "script_id" not in extra_details:
        versionedtextfile = await create_test_versionedtextfile_entry(fixture)
        extra_details["script_id"] = versionedtextfile["id"]

    script = {
        "created": created_at,
        "updated": updated_at,
        "name": name,
        "title": name,
        "description": "",
        "tags": [],
        "script_type": ScriptType.COMMISSIONING,
        "timeout": timedelta(),
        "destructive": False,
        "default": False,
        "hardware_type": HardwareDeviceTypeEnum.NODE,
        "packages": {},
        "parallel": ScriptParallel.DISABLED,
        "parameters": {},
        "results": {},
        "for_hardware": [],
        "may_reboot": False,
        "recommission": False,
        "apply_configured_networking": False,
    }
    script.update(extra_details)

    [created_script] = await fixture.create(ScriptTable.name, script)
    return Script(**created_script)
