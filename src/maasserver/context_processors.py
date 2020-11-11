# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Context processors."""


from django.conf import settings

from maasserver.config import RegionConfiguration
from maasserver.models import Config, RegionController
from provisioningserver.utils.version import (
    get_maas_doc_version,
    get_maas_version_ui,
)


def global_options(request):
    version = get_maas_version_ui()
    uuid = RegionController.objects.get_or_create_uuid()
    with RegionConfiguration.open() as config:
        maas_url = config.maas_url
    configs = Config.objects.get_configs(
        [
            "maas_name",
            "enable_analytics",
            "rpc_shared_secret",
            "completed_intro",
        ]
    )
    user_completed_intro = False
    completed_intro = configs["completed_intro"]
    if not hasattr(request, "user"):
        return {}
    if hasattr(request.user, "userprofile"):
        user_completed_intro = request.user.userprofile.completed_intro
    if not completed_intro and not request.user.is_superuser:
        # Only administrators can completed the main intro, normal users
        # cannot complete it so to them it has been done.
        completed_intro = True
    if request.user.is_authenticated:
        analytics_user_id = "%s-user%d" % (uuid, request.user.id)
    else:
        analytics_user_id = "%s-anon" % uuid
    return {
        "global_options": {
            "site_name": configs["maas_name"],
            "enable_analytics": configs["enable_analytics"],
        },
        "debug": settings.DEBUG,
        "version": version,
        "files_version": version.replace(" ", ""),
        "doc_version": get_maas_doc_version(),
        "register_url": maas_url,
        "register_secret": configs["rpc_shared_secret"],
        "completed_intro": completed_intro,
        "user_completed_intro": user_completed_intro,
        "analytics_user_id": analytics_user_id,
        "maas_uuid": uuid,
    }
