# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: MAAS."""

import json

from django.http import HttpResponse
from formencode import validators
from piston3.utils import rc

from maasserver.api.support import admin_method, operation, OperationsHandler
from maasserver.api.utils import get_mandatory_param
from maasserver.enum import ENDPOINT
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import UbuntuForm
from maasserver.forms.settings import (
    get_config_doc,
    get_config_form,
    validate_config_name,
)
from maasserver.models import Config, PackageRepository


class MigratedConfigValue:
    """Some settings have been moved out of the Config system. To allow these
    values to continue to be accessed via this API, the Form and getter method
    are overridable here."""

    def __init__(self, form, getter):
        self.form = form
        self.getter = getter


migrated_config_values = {
    "main_archive": MigratedConfigValue(
        UbuntuForm, PackageRepository.get_main_archive_url
    ),
    "ports_archive": MigratedConfigValue(
        UbuntuForm, PackageRepository.get_ports_archive_url
    ),
}


def rewrite_config_name(name):
    """Rewrite the config name for backwards compatibility."""
    return "ntp_servers" if name == "ntp_server" else name


def get_maas_form(name, value):
    """Get the Form for the provided name. Most names use a ConfigForm, but
    some names have been moved out of the Config database and now use different
    forms. The new form is instantiated here and returned to provide continued
    access to the values when using this API."""
    if name in migrated_config_values:
        form = migrated_config_values[name].form(data={})
        # Copy all initial values to data then set provided value.
        form.data = form.initial.copy()
        form.data[name] = value
        return form
    return get_config_form(name, {name: value})


class MaasHandler(OperationsHandler):
    """Manage the MAAS server."""

    api_doc_section_name = "MAAS server"
    create = read = update = delete = None

    @admin_method
    @operation(idempotent=False)
    def set_config(self, request):
        """@description-title Set a configuration value
        @description Set a configuration value.

        @param (string) "value" [required=false] The value of the configuration
        item to be set.

        @param (string) "name" [required=true,formatting=true] The name of the
        configuration item to be set.

        %s

        @success (http-status-code) "server-success" 200
        @success (content) "set-success" A plain-text string
        @success-example "set-success"
            OK
        """
        name = get_mandatory_param(
            request.data, "name", validators.String(min=1)
        )
        name = rewrite_config_name(name)
        value = get_mandatory_param(request.data, "value")
        form = get_maas_form(name, value)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        form.save(ENDPOINT.API, request)
        return rc.ALL_OK

    # Populate the docstring with the dynamically-generated documentation
    # about the available configuration items.
    set_config.__doc__ %= get_config_doc(indentation=8)

    @operation(idempotent=True)
    def get_config(self, request):
        """@description-title Get a configuration value
        @description Get a configuration value.

        @param (string) "name" [required=true,formatting=true] The name of the
        configuration item to be retrieved.

        %s

        @success (http-status-code) "server-success" 200
        @success (content) "default_distro_series" A plain-text string
        containing the requested value, e.g. ``default_distro_series``.
        @success-example "default_distro_series"
            "bionic"
        """
        name = get_mandatory_param(request.GET, "name")
        name = rewrite_config_name(name)
        if name in migrated_config_values:
            value = migrated_config_values[name].getter()
        else:
            validate_config_name(name)
            value = Config.objects.get_config(name)
        return HttpResponse(json.dumps(value), content_type="application/json")

    # Populate the docstring with the dynamically-generated documentation
    # about the available configuration items.
    get_config.__doc__ %= get_config_doc(indentation=8)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("maas_handler", [])
