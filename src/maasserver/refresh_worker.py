# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Refresh node-group worker's knowledge."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'refresh_worker',
    ]

from apiclient.creds import convert_tuple_to_string
from maasserver.models.user import get_creds_tuple
from provisioningserver.tasks import refresh_secrets


def refresh_worker(nodegroup):
    """Send worker for `nodegroup` a refresh message with credentials etc.

    This is how we tell the worker its MAAS API credentials, the name of
    the node group it manages, and so on.  The function gathers all the
    usual information (although we can always extend the mechanism with
    more specific knowledge that we may choose not to include here) and
    issues a task to the node-group worker that causes it to absorb the
    given information items.
    """

    items = {
        'api_credentials': convert_tuple_to_string(
            get_creds_tuple(nodegroup.api_token)),
        'nodegroup_uuid': nodegroup.uuid,
    }

    refresh_secrets.apply_async(queue=nodegroup.work_queue, kwargs=items)
