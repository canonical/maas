#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasservicelayer.db.tables import ScriptSetTable
from metadataserver.enum import RESULT_TYPE
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_scriptset_entry(
    fixture: Fixture,
    node_id: int,
    **extra_details: Any,
) -> dict[str, Any]:
    """
    Create an entry in the ScriptSetTable. This function must be used only for
    testing.

    The script set contains a reference to a collection of scripts that was run
    against a node at one point during its life cycle. For example, the script
    set run during commissioning.

    In order to create a script set entry, the following parameters should be
    defined:
    - node_id: ID of the node where the script set ran. This ID is the primary
      key of the node table.

    Note that due to the testing purpose of this function, node_id is not
    validated against the Node table. It is up to the user to decide how to
    proceed.
    """
    scriptset = {
        "node_id": node_id,
        "result_type": RESULT_TYPE.COMMISSIONING,
        "power_state_before_transition": "",
    }
    scriptset.update(extra_details)

    [created_scriptset] = await fixture.create(ScriptSetTable.name, scriptset)

    return created_scriptset
