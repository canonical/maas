#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from typing import Any

from maasservicelayer.db.tables import TagTable
from tests.maasapiserver.fixtures.db import Fixture

"""Factory of TagTable entries."""


async def create_test_tag_entry(
    fixture: Fixture,
    name: str,
    definition: str,
    **extra_details: Any,
) -> dict[str, Any]:
    """
    Create an entry in the TagTable. This function must be used only for
    testing.

    A tag is used to identify a node in MAAS, and most of the time the tag is
    defined by a user to group machines.

    There are two types of tags: manual and automatic. The latest are the type
    of tags tracked in the TagTable.

    In order to create a tag entry, the following parameters should be defined:
    - name: this is the name of the tag, and can be used as human friendly
      identifier due to its uniqueness constraint.
      Examples of names are: tag-101, arm64_machine, testing
    - definition: this is an XPath expression that allows MAAS to automatically
      match the tag with a node. The expression is evaluated against the
      `stdout` of some of the scripts that run in the node during
      commissioning.
      Examples of definitions are: //node, //vendor[text()="Vendor X"]

    Note that even if both arguments can be empty strings, that would defeat
    the purpose of defining the tag.

    Learn more about tagging in https://maas.io/docs
    """
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    tag = {
        "created": created_at,
        "updated": updated_at,
        "name": name,
        "definition": definition,
        "comment": "",
        "kernel_opts": "",
    }
    tag.update(extra_details)

    [created_tag] = await fixture.create(TagTable.name, tag)

    return created_tag
