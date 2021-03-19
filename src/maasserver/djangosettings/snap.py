# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django snap settings for maas project."""

import os

from maasserver.djangosettings import import_settings, settings

# Extend base and development settings.
import_settings(settings)

# Override the location of JS libraries.
JQUERY_LOCATION = os.path.join(
    os.environ["SNAP"], "usr", "share", "javascript", "jquery"
)
ANGULARJS_LOCATION = os.path.join(
    os.environ["SNAP"], "usr", "share", "javascript", "angular.js"
)

# Override path to static root.
STATIC_ROOT = os.path.join(
    os.environ["SNAP"], "usr", "share", "maas", "web", "static"
)

# Override the preseed locations.
PRESEED_TEMPLATE_LOCATIONS = (
    os.path.join(os.environ["SNAP_DATA"], "preseeds"),
    os.path.join(os.environ["SNAP"], "etc", "maas", "preseeds"),
)
