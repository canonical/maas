# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for the metadata server.

DO NOT add new models to this module.  Add them to the package as separate
modules, but import them here and add them to `__all__`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'NodeCommissionResult',
    'NodeKey',
    'NodeUserData',
    ]

from maasserver.utils import ignore_unused
from metadataserver.models.nodecommissionresult import NodeCommissionResult
from metadataserver.models.nodekey import NodeKey
from metadataserver.models.nodeuserdata import NodeUserData


ignore_unused(NodeCommissionResult, NodeKey, NodeUserData)
