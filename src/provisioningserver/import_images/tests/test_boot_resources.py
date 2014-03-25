# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the boot_resources module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import errno
import os
from random import randint

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import MagicMock
from provisioningserver.config import Config
from provisioningserver.import_images import boot_resources
from provisioningserver.import_images.boot_resources import (
    main,
    NoConfigFile,
    )


class TestMain(MAASTestCase):

    def test_raises_ioerror_when_no_config_file_found(self):
        # Suppress log output.
        self.logger = self.patch(boot_resources, 'logger')
        filename = "/tmp/%s" % factory.make_name("config")
        self.assertFalse(os.path.exists(filename))
        args = MagicMock()
        args.config_file = filename
        self.assertRaises(NoConfigFile, main, args)

    def test_raises_non_ENOENT_IOErrors(self):
        # main() will raise a NoConfigFile error when it encounters an
        # ENOENT IOError, but will otherwise just re-raise the original
        # IOError.
        args = MagicMock()
        mock_load_from_cache = self.patch(Config, 'load_from_cache')
        other_error = IOError(randint(errno.ENOENT + 1, 1000))
        mock_load_from_cache.side_effect = other_error
        # Suppress log output.
        self.logger = self.patch(boot_resources, 'logger')
        raised_error = self.assertRaises(IOError, main, args)
        self.assertEqual(other_error, raised_error)
