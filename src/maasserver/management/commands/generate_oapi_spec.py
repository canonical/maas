# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: generate the Open API specification."""

from django.core.management.base import BaseCommand
import yaml

from maasserver.api.doc_oapi import get_api_endpoint


class Command(BaseCommand):
    def handle(self, *args, **options):
        oapi = get_api_endpoint()
        oapi["externalDocs"]["url"] = "https://maas.io/docs"
        self.stdout.write(yaml.dump(oapi))
