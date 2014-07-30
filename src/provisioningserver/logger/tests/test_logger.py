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

import logging

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.logger import log
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.testing.testcase import PservTestCase


class TestGetMAASLogger(PservTestCase):

    def test_logger_logs_to_syslog(self):
        handler = self.patch(log, 'SysLogHandler')
        self.patch(logging, 'Formatter')
        maaslog = get_maas_logger()
        random_log_text = factory.make_string()
        maaslog.warn(random_log_text)
        self.assertThat(
            handler.return_value.setFormatter,
            MockCalledOnceWith(logging.Formatter.return_value))
        self.assertThat(
            handler, MockCalledOnceWith("/dev/log"))
        # For future hackers, handler.emit should be getting called here
        # but it's not.  NFI why.  HALP.

    def test_adds_custom_formatting(self):
        self.patch(log, 'SysLogHandler')
        formatter = self.patch(logging, 'Formatter')
        extra_formatting = factory.make_string()
        get_maas_logger(extra_formatting)
        self.assertThat(
            formatter,
            MockCalledOnceWith(
                fmt=("maas.%s:" % extra_formatting) +
                " [%(levelname)s] %(message)s"))

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
