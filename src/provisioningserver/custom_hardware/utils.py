# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from logging import getLogger

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
    )
from provisioningserver.auth import get_recorded_api_credentials
from provisioningserver.cluster_config import get_maas_url


logger = getLogger(__name__)


def create_node(mac, arch, power_type, power_parameters):
    api_credentials = get_recorded_api_credentials()
    if api_credentials is None:
        raise Exception('Not creating node: no API key yet.')
    client = MAASClient(
        MAASOAuth(*api_credentials), MAASDispatcher(),
        get_maas_url())

    data = {
        'op': 'new',
        'architecture': arch,
        'power_type': power_type,
        'power_parameters': power_parameters,
        'mac_addresses': mac
    }
    return client.post('/api/1.0/nodes/', data)
