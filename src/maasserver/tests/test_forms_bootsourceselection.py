# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceSelectionForm`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.forms import BootSourceSelectionForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestBootSourceSelectionForm(MAASServerTestCase):
    """Tests for `BootSourceSelectionForm`."""

    def test_edits_boot_source_selection_object(self):
        boot_source_selection = factory.make_BootSourceSelection()
        params = {
            'os': factory.make_name('os'),
            'release': factory.make_name('release'),
            'arches': [factory.make_name('arch'), factory.make_name('arch')],
            'subarches': [
                factory.make_name('subarch'), factory.make_name('subarch')],
            'labels': [factory.make_name('label'), factory.make_name('label')],
        }
        form = BootSourceSelectionForm(
            instance=boot_source_selection, data=params)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        boot_source_selection = reload_object(boot_source_selection)
        self.assertAttributes(boot_source_selection, params)

    def test_creates_boot_source_selection_object(self):
        boot_source = factory.make_boot_source()
        params = {
            'os': factory.make_name('os'),
            'release': factory.make_name('release'),
            'arches': [factory.make_name('arch'), factory.make_name('arch')],
            'subarches': [
                factory.make_name('subarch'), factory.make_name('subarch')],
            'labels': [factory.make_name('label'), factory.make_name('label')],
        }
        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)
        boot_source_selection = form.save()
        self.assertAttributes(boot_source_selection, params)
