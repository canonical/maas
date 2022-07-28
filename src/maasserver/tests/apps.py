# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.apps import AppConfig


class MAASServerTestsConfig(AppConfig):
    name = "maasserver.tests"
    label = "maasserver_tests"
