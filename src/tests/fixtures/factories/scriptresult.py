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

    Each script result entry contains information with the results of running a
    script in a node controlled by MAAS.
    When a script runs, it does it as part of a collection of scripts. The
    information about that collection is stored in the ScriptSetTable.
    Some of these scripts, such as maas-lshw (used for tag evaluation), can be
    found in src/provisioningserver/refresh/.

    In order to create a script result entry, the following parameters should
    be defined:
    - script_set_id: reference to the entry of the ScriptSetTable. This entry
      contains the information about the script set where the script belong to.

    Note that due to the testing purpose of this function, script_set_id is not
    validated against the ScriptSetTable. It is up to the user to decide how to
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
