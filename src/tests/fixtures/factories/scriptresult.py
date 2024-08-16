#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Any

from maasservicelayer.db.tables import ScriptResultTable
from metadataserver.enum import SCRIPT_STATUS
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_scriptresult_entry(
    fixture: Fixture,
    script_set_id: int,
    **extra_details: Any,
) -> dict[str, Any]:
    """
    Create an entry in the ScriptResultTable. This function must be used only
    for testing.

    A script result entry contains information about the outcome of running a
    script in a node controlled by MAAS.
    When a script runs, it does as part of a set of scripts that can have one
    or more scripts. This set of scripts are stored in the ScriptSetTable.
    Some of these scripts, such as maas-lshw used for tag evaluation, can be
    found in src/provisioningserver/refresh/.

    In order to create a script result entry, the following parameters should
    be defined:
    - script_set_id: every script must belong to a script set that gathers one
      or more scripts based on their purpose. This field contains the ID of the
      script set where the script belongs to.

    Note that due to the testing purpose of this function, node_id is not
    validated against the Node table. It is up to the user to decide how to
    proceed.
    """
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()

    scriptresult = {
        "created": created_at,
        "updated": updated_at,
        "status": SCRIPT_STATUS.PASSED,
        "stdout": "",
        "stderr": "",
        "result": "",
        "script_set_id": script_set_id,
        "output": "",
        "parameters": {},
        "suppressed": False,
    }
    scriptresult.update(extra_details)

    [created_scriptresult] = await fixture.create(
        ScriptResultTable.name, scriptresult
    )

    return created_scriptresult
