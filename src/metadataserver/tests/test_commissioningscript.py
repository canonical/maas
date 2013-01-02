# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom commissioning scripts."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from io import BytesIO
from math import (
    ceil,
    floor,
    )
import os.path
from random import randint
import tarfile
import time

from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maastesting.matchers import ContainsAll
from maastesting.utils import sample_binary_data
from metadataserver.fields import Bin
from metadataserver.models import (
    CommissioningScript,
    commissioningscript as cs_module,
    )
from metadataserver.models.commissioningscript import ARCHIVE_PREFIX


def open_tarfile(content):
    """Open tar file from raw binary data."""
    return tarfile.open(fileobj=BytesIO(content))


def make_script_name(base_name=None, number=None):
    """Make up a name for a commissioning script."""
    if base_name is None:
        base_name = 'script'
    if number is None:
        number = randint(0, 99)
    return factory.make_name(
        '%0.2d-%s' % (number, factory.make_name(base_name)))


class TestCommissioningScriptManager(TestCase):

    def test_get_archive_wraps_scripts_in_tar(self):
        script = factory.make_commissioning_script()
        path = os.path.join(ARCHIVE_PREFIX, script.name)
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertTrue(archive.getmember(path).isfile())
        self.assertEqual(script.content, archive.extractfile(path).read())

    def test_get_archive_wraps_all_scripts(self):
        scripts = {factory.make_commissioning_script() for counter in range(3)}
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertThat(
            archive.getnames(),
            ContainsAll({
                os.path.join(ARCHIVE_PREFIX, script.name)
                for script in scripts
                }))

    def test_get_archive_supports_binary_scripts(self):
        script = factory.make_commissioning_script(content=sample_binary_data)
        path = os.path.join(ARCHIVE_PREFIX, script.name)
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertEqual(script.content, archive.extractfile(path).read())

    def test_get_archive_includes_builtin_scripts(self):
        name = factory.make_name('00-maas')
        path = os.path.join(ARCHIVE_PREFIX, name)
        content = factory.getRandomString().encode('ascii')
        self.patch(cs_module, 'BUILTIN_COMMISSIONING_SCRIPTS', {name: content})
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertIn(path, archive.getnames())
        self.assertEqual(content, archive.extractfile(path).read())

    def test_get_archive_sets_sensible_mode(self):
        for counter in range(3):
            factory.make_commissioning_script()
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertEqual({0755}, {info.mode for info in archive.getmembers()})

    def test_get_archive_initializes_file_timestamps(self):
        # The mtime on a file inside the tarball is reasonable.
        # It would otherwise default to the Epoch, and GNU tar warns
        # annoyingly about improbably old files.
        start_time = floor(time.time())
        script = factory.make_commissioning_script()
        path = os.path.join(ARCHIVE_PREFIX, script.name)
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        timestamp = archive.getmember(path).mtime
        end_time = ceil(time.time())
        self.assertGreaterEqual(timestamp, start_time)
        self.assertLessEqual(timestamp, end_time)


class TestCommissioningScript(TestCase):

    def test_scripts_may_be_binary(self):
        name = make_script_name()
        CommissioningScript.objects.create(
            name=name, content=Bin(sample_binary_data))
        stored_script = CommissioningScript.objects.get(name=name)
        self.assertEqual(sample_binary_data, stored_script.content)
