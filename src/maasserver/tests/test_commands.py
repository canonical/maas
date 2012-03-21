# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom commands, as found in src/maasserver/management/commands."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os

from django.conf import settings
from django.core.management import call_command
from maasserver.models import FileStorage
from maastesting.testcase import TestCase


class TestCommands(TestCase):
    """Happy-path integration testing for custom commands.

    Detailed testing does not belong here.  If there's any complexity at all
    in a command's code, it should be extracted and unit-tested separately.
    """

    def test_gc(self):
        upload_dir = os.path.join(settings.MEDIA_ROOT, FileStorage.upload_dir)
        os.makedirs(upload_dir)
        self.addCleanup(os.removedirs, upload_dir)
        call_command('gc')
        # The test is that we get here without errors.
        pass
