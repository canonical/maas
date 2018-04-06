# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test GlobalDefault objects."""

from maasserver.models import (
    Domain,
    GlobalDefault,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import Equals


class TestGlobalDefault(MAASServerTestCase):
    """Tests for :class:`GlobalDefault`."""

    def test_get_instance_creates_instance_id_0_if_none_exits(self):
        instance = GlobalDefault.objects.instance()
        self.assertThat(instance.id, Equals(0))

    def test_get_instance_returns_existing_id_0(self):
        GlobalDefault.objects.instance()
        instance = GlobalDefault.objects.instance()
        self.assertThat(instance.id, Equals(0))

    def test_returns_default_domain(self):
        instance = GlobalDefault.objects.instance()
        self.assertThat(instance.domain, Equals(
            Domain.objects.get_default_domain()))

    def test_default_domain_changes_take_effect(self):
        instance = GlobalDefault.objects.instance()
        instance.domain = factory.make_Domain()
        instance.save()
        self.assertThat(instance.domain, Equals(
            Domain.objects.get_default_domain()))
