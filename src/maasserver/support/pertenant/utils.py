# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the per-tenant file storage work."""

import yaml

from maasserver.models import FileStorage, Node

PROVIDER_STATE_FILENAME = "provider-state"


def get_bootstrap_node_owner():
    """Return the owner of the bootstrap node or None if it cannot be found.

    This method uses the unowned 'provider-state' file to extract the system_id
    of the bootstrap node.
    """
    try:
        provider_file = FileStorage.objects.get(
            filename=PROVIDER_STATE_FILENAME, owner=None
        )
    except FileStorage.DoesNotExist:
        return None
    system_id = extract_bootstrap_node_system_id(provider_file.content)
    if system_id is None:
        return None
    try:
        return Node.objects.get(system_id=system_id).owner
    except Node.DoesNotExist:
        return None


def extract_bootstrap_node_system_id(content):
    """Extract the system_id of the node referenced in the given
    provider-state file.

    This method implements a very defensive strategy; if the given
    content is not in yaml format or if the owner of the bootstrap
    node cannot be found, it returns None.
    """
    try:
        state = yaml.safe_load(content)
    except yaml.YAMLError:
        return None
    try:
        parts = state["zookeeper-instances"][0].split("/")
    except (IndexError, TypeError):
        return None
    system_id = [part for part in parts if part != ""][-1]
    return system_id
