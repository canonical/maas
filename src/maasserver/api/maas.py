# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: MAAS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'MaasHandler',
    ]


from django.http import HttpResponse
from formencode import validators
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_mandatory_param
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_settings import (
    get_config_doc,
    get_config_form,
    validate_config_name,
)
from maasserver.models import Config
from piston.utils import rc
import simplejson as json


class MaasHandler(OperationsHandler):
    """Manage the MAAS server."""
    api_doc_section_name = "MAAS server"
    create = read = update = delete = None

    @operation(idempotent=False)
    def set_config(self, request):
        """Set a config value.

        :param name: The name of the config item to be set.
        :type name: unicode
        :param value: The value of the config item to be set.
        :type value: json object

        %s
        """
        name = get_mandatory_param(
            request.data, 'name', validators.String(min=1))
        value = get_mandatory_param(request.data, 'value')
        form = get_config_form(name, {name: value})
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        form.save()
        return rc.ALL_OK

    # Populate the docstring with the dynamically-generated documentation
    # about the available configuration items.
    set_config.__doc__ %= get_config_doc(indentation=8)

    @operation(idempotent=True)
    def get_config(self, request):
        """Get a config value.

        :param name: The name of the config item to be retrieved.
        :type name: unicode

        %s
        """
        name = get_mandatory_param(request.GET, 'name')
        validate_config_name(name)
        value = Config.objects.get_config(name)
        return HttpResponse(json.dumps(value), content_type='application/json')

    # Populate the docstring with the dynamically-generated documentation
    # about the available configuration items.
    get_config.__doc__ %= get_config_doc(indentation=8)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('maas_handler', [])
