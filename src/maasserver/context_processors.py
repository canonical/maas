# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Context processors."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "global_options",
    "yui",
    ]

from django.conf import settings
from maasserver.components import get_persistent_errors
from maasserver.models import Config
from maasserver.utils.version import (
    get_maas_doc_version,
    get_maas_version_ui,
)


def yui(context):
    return {
        'YUI_DEBUG': settings.YUI_DEBUG,
    }


def global_options(context):
    version = get_maas_version_ui()
    return {
        'persistent_errors': get_persistent_errors(),
        'global_options': {
            'site_name': Config.objects.get_config('maas_name'),
        },
        'debug': settings.DEBUG,
        'version': version,
        'files_version': version.replace(" ", ""),
        'doc_version': get_maas_doc_version(),
    }
