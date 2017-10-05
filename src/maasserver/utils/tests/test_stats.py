# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test stats utilities."""

__all__ = []

import base64
import json

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.stats import (
    get_maas_stats,
    get_request_params,
    make_maas_user_agent_request,
)
from maastesting.matchers import MockCalledOnce
import requests as requests_module


class TestMAASStats(MAASServerTestCase):

    def test_get_maas_stats(self):
        # Make one component of everything
        factory.make_RegionRackController()
        factory.make_RegionController()
        factory.make_RackController()
        factory.make_Machine()
        factory.make_Device()

        stats = get_maas_stats()
        compare = {
            "controllers": {
                "regionracks": 1,
                "regions": 1,
                "racks": 1,
            },
            "nodes": {
                "machines": 1,
                "devices": 1,
            },
        }
        self.assertEquals(stats, json.dumps(compare))

    def test_get_request_params_returns_params(self):
        factory.make_RegionRackController()
        params = {
            "data": base64.b64encode(
                json.dumps(get_maas_stats()).encode()).decode()
        }
        self.assertEquals(params, get_request_params())

    def test_make_user_agent_request(self):
        factory.make_RegionRackController()
        mock = self.patch(requests_module, "get")
        make_maas_user_agent_request()
        self.assertThat(mock, MockCalledOnce())
