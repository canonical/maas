# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver`."""

from django.apps import AppConfig


class MAASServerTestsConfig(AppConfig):
    name = "maasserver.tests"
    label = "maasserver_tests"


default_app_config = "maasserver.tests.MAASServerTestsConfig"
