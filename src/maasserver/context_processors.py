# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Context processors."""

__all__ = [
    "global_options",
    "yui",
    ]

from django.conf import settings
from maasserver.components import get_persistent_errors
from maasserver.config import RegionConfiguration
from maasserver.models import Config
from maasserver.utils.version import (
    get_maas_doc_version,
    get_maas_version_ui,
)


def yui(request):
    return {
        'YUI_DEBUG': settings.YUI_DEBUG,
    }


def global_options(request):
    version = get_maas_version_ui()
    with RegionConfiguration.open() as config:
        maas_url = config.maas_url
    user_completed_intro = False
    if hasattr(request.user, 'userprofile'):
        user_completed_intro = request.user.userprofile.completed_intro
    return {
        'persistent_errors': get_persistent_errors(),
        'global_options': {
            'site_name': Config.objects.get_config('maas_name'),
            'enable_analytics': Config.objects.get_config('enable_analytics'),
        },
        'debug': settings.DEBUG,
        'version': version,
        'files_version': version.replace(" ", ""),
        'doc_version': get_maas_doc_version(),
        'register_url': maas_url,
        'register_secret': Config.objects.get_config('rpc_shared_secret'),
        'completed_intro': Config.objects.get_config('completed_intro'),
        'user_completed_intro': user_completed_intro,
    }
