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

import logging.handlers
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.testing.testcase import PservTestCase


class TestMAASLog(PservTestCase):

    def test_logs_to_syslog(self):
        handler = self.patch(logging.handlers, 'SysLogHandler')
        from provisioningserver.logger.log import maaslog
        from provisioningserver.logger import log
        random_log_text = factory.make_string()
        maaslog.warn(random_log_text)
        self.assertThat(
            handler.return_value.setFormatter,
            MockCalledOnceWith(log.formatter))
        self.assertThat(
            handler, MockCalledOnceWith("/dev/log"))
        # For future hackers, handler.emit should be getting called here
        # but it's not.  NFI why.  HALP.
