# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.testing.factory import factory
from maasserver.websockets.handlers.machine import MachineHandler
from maastesting.perftest import perf_test


@perf_test(db_only=True)
def test_perf_list_machines_Websocket_endpoint():
    user = factory.make_admin()
    ws_handler = MachineHandler(user, {}, None)
    ws_handler.list({})
