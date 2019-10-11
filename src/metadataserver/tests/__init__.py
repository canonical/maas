# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `metadataserver`."""

from django.apps import AppConfig


class MetadataServerTestsConfig(AppConfig):
    name = "metadataserver.tests"
    label = "metadataserver_tests"


default_app_config = "metadataserver.tests.MetadataServerTestsConfig"
