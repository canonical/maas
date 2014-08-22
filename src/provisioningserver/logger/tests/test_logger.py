# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for log.py"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from itertools import imap
import logging
import logging.handlers

from maastesting.factory import factory
from provisioningserver.logger import log
from provisioningserver.logger.log import (
    get_maas_logger,
    MAASLogger,
    )
from provisioningserver.testing.testcase import PservTestCase
from testtools.matchers import (
    HasLength,
    IsInstance,
    )


class TestGetMAASLogger(PservTestCase):

    def test_root_logger_logs_to_syslog(self):
        root_logger = get_maas_logger()
        self.assertThat(root_logger.handlers, HasLength(1))
        [handler] = root_logger.handlers
        self.assertThat(handler, IsInstance(logging.handlers.SysLogHandler))

    def test_root_logger_defaults_to_info(self):
        root_logger = get_maas_logger()
        self.assertEqual(logging.INFO, root_logger.level)

    def test_does_not_log_twice(self):
        maas_logger = get_maas_logger()
        maas_foo_logger = get_maas_logger("foo")

        all_handlers = []
        # In previous versions of get_maas_logger(), the all_handlers list
        # would end up containing two handlers, because a new SysLogHandler
        # was added to each logger. This means that logging to the "maas.foo"
        # logger would emit a message to syslog via its handler, then the log
        # record would be propagated up to the "maas" logger (which we're
        # calling the root logger in this context) where its handler would
        # then emit another message to syslog.
        all_handlers.extend(maas_logger.handlers)
        all_handlers.extend(maas_foo_logger.handlers)
        self.expectThat(all_handlers, HasLength(1))

        # Intercept calls to `emit` on each handler above.
        log_records = []
        for handler in all_handlers:
            self.patch(handler, "emit", log_records.append)

        maas_foo_logger.info("A message from the Mekon")

        self.assertThat(log_records, HasLength(1))

    def test_sets_custom_formatting(self):
        logger = get_maas_logger("foo.bar")
        [handler] = get_maas_logger().handlers
        log_records = []
        self.patch(handler, "emit", log_records.append)

        robot_name = factory.make_name("Robot")
        logger.info("Hello there %s!", robot_name)

        self.assertEqual(
            "maas.foo.bar: [INFO] Hello there %s!" % robot_name,
            "\n---\n".join(imap(handler.format, log_records)))

    def test_sets_logger_name(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        self.assertEqual("maas.%s" % name, maaslog.name)

    def test_returns_same_logger_if_called_twice(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        maaslog_2 = get_maas_logger(name)
        self.assertIs(maaslog, maaslog_2)

    def test_exception_calls_disallowed(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        self.assertRaises(
            NotImplementedError, maaslog.exception,
            factory.make_string())

    def test_returns_MAASLogger_instances(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        maaslog = get_maas_logger(name)
        self.assertIsInstance(maaslog, MAASLogger)

    def test_doesnt_affect_general_logger_class(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        get_maas_logger(name)
        self.assertIsNot(
            MAASLogger, logging.getLoggerClass())

    def test_general_logger_class_accepts_exceptions(self):
        self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        name = factory.make_string()
        get_maas_logger(name)
        other_logger = logging.getLogger()
        self.assertIsNone(other_logger.exception(factory.make_string()))
