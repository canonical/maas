# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    'RegionControllerHandler',
    'RegionControllersHandler',
    ]

from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
)
from maasserver.models import RegionController

# Region controller's fields exposed on the API.
DISPLAYED_REGION_CONTROLLER_FIELDS = (
    'system_id',
    'hostname',
    'domain',
    'fqdn',
    'architecture',
    'cpu_count',
    'memory',
    'swap_size',
    'osystem',
    'distro_series',
    'ip_addresses',
    ('interface_set', (
        'id',
        'name',
        'type',
        'vlan',
        'mac_address',
        'parents',
        'children',
        'tags',
        'enabled',
        'links',
        'params',
        'discovered',
        'effective_mtu',
        )),
    'zone',
    'status_action',
    'node_type',
    'node_type_name',
)


class RegionControllerHandler(NodeHandler):
    """Manage an individual region controller.

    The region controller is identified by its system_id.
    """
    api_doc_section_name = "RegionController"
    model = RegionController
    fields = DISPLAYED_REGION_CONTROLLER_FIELDS

    @classmethod
    def resource_uri(cls, regioncontroller=None):
        regioncontroller_id = "system_id"
        if regioncontroller is not None:
            regioncontroller_id = regioncontroller.system_id
        return ('regioncontroller_handler', (regioncontroller_id, ))


class RegionControllersHandler(NodesHandler):
    """Manage the collection of all region controllers in MAAS."""
    api_doc_section_name = "RegionControllers"
    base_model = RegionController

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('regioncontrollers_handler', [])
