# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `p.logger._maaslog`."""

import logging
import logging.handlers

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.logger import _maaslog
from provisioningserver.logger._maaslog import get_maas_logger, MAASLogger


class TestMAASLogger(MAASTestCase):
    """Tests for the logger returned by `get_maas_logger`."""

    def test_sets_logger_name(self):
        self.patch(_maaslog, "SysLogHandler")
        self.patch(logging, "Formatter")
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        self.assertEqual("maas.%s" % name, maaslog.name)

    def test_returns_same_logger_if_called_twice(self):
        self.patch(_maaslog, "SysLogHandler")
        self.patch(logging, "Formatter")
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        maaslog_2 = get_maas_logger(name)
        self.assertIs(maaslog, maaslog_2)

    def test_exception_calls_disallowed(self):
        self.patch(_maaslog, "SysLogHandler")
        self.patch(logging, "Formatter")
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        self.assertRaises(
            NotImplementedError, maaslog.exception, factory.make_string()
        )

    def test_returns_MAASLogger_instances(self):
        self.patch(_maaslog, "SysLogHandler")
        self.patch(logging, "Formatter")
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        self.assertIsInstance(maaslog, MAASLogger)

    def test_doesnt_affect_general_logger_class(self):
        self.patch(logging, "Formatter")
        name = factory.make_string()
        get_maas_logger(name)
        self.assertIsNot(MAASLogger, logging.getLoggerClass())

    def test_general_logger_class_accepts_exceptions(self):
        self.patch(logging, "Formatter")
        name = factory.make_string()
        get_maas_logger(name)
        other_logger = logging.getLogger()
        self.assertIsNone(other_logger.exception(factory.make_string()))
