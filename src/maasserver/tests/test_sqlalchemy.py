#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.engine import base as sqlalchemy_base_module

from maasserver.sqlalchemy import InvalidConnection, service_layer
from maasserver.testing.testcase import SerializationFailureTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.tests.test_orm import NoSleepMixin
from maasservicelayer.models.configurations import MAASUrlConfig


class TestServiceLayerInTransaction(
    SerializationFailureTestCase, NoSleepMixin
):
    def test_sqlalchemy_connection_transaction_is_retried(self):
        watcher = {"count": 0}

        @transactional
        def _in_transaction():
            watcher["count"] += 1
            service_layer.services.configurations.get("")

        _execute_context_mock = self.patch(
            sqlalchemy_base_module.Connection, "_execute_context"
        )
        _execute_context_mock.side_effect = InvalidConnection()

        self.assertRaises(InvalidConnection, _in_transaction)
        self.assertEqual(10, watcher["count"])

    def test_sqlalchemy_connection_replaced_when_transaction_is_retried(self):
        watcher = {"count": 0}

        def disconnect_django():
            from django.db import connections

            for conn in connections.all():
                conn.close()

        @transactional
        def _in_transaction():
            watcher["count"] += 1
            if watcher["count"] == 1:
                # On the first attempt, simulate a Django disconnection. When the transaction is retried, @transactional should
                # establish a new connection and the service layer is expected to pick it as well.
                disconnect_django()
            return service_layer.services.configurations.get(
                MAASUrlConfig.name
            )

        result = _in_transaction()
        self.assertEqual(MAASUrlConfig.default, result)
        self.assertEqual(2, watcher["count"])
