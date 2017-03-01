# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.pod`"""

__all__ = []

from maasserver.forms.pods import PodForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.pod import PodHandler
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.drivers.pod import Capabilities
from testtools.matchers import Equals


class TestPodHandler(MAASServerTestCase):

    def dehydrate_pod(self, pod):
        data = {
            "id": pod.id,
            "name": pod.name,
            "cpu_speed": pod.cpu_speed,
            "power_type": pod.power_type,
            "ip_address": pod.ip_address,
            "updated": dehydrate_datetime(pod.updated),
            "created": dehydrate_datetime(pod.created),
            "total": {
                "cores": pod.cores,
                "memory": pod.memory,
                "local_storage": pod.local_storage,
                },
            "used": {
                "cores": pod.get_used_cores(),
                "memory": pod.get_used_memory(),
                "local_storage": pod.get_used_local_storage(),
                },
            "capabilities": pod.capabilities,
            "architectures": pod.architectures,
            }
        if Capabilities.FIXED_LOCAL_STORAGE in pod.capabilities:
            data['total']['local_disks'] = pod.local_disks
            data['used']['local_disks'] = pod.get_used_local_disks()
        available = {}
        for key, value in data['total'].items():
            available[key] = value - data['used'][key]
        data['available'] = available
        return data

    def test_get(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {})
        pod = factory.make_Pod()
        expected_data = self.dehydrate_pod(pod)
        result = handler.get({"id": pod.id})
        self.assertThat(result, Equals(expected_data))

    def test_refresh_refreshes(self):
        user = factory.make_User()
        handler = PodHandler(user, {})
        pod = factory.make_Pod()
        mock_discover_and_sync_pod = self.patch(
            PodForm, 'discover_and_sync_pod')
        handler.refresh({"id": pod.id})
        self.assertThat(
            mock_discover_and_sync_pod, MockCalledOnceWith())
