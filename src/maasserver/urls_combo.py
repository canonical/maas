# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL combo routing configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


from django.conf import settings as django_settings
from django.conf.urls.defaults import (
    patterns,
    url,
    )
from maasserver.views.combo import get_combo_view


urlpatterns = patterns('',
    url(
        r'^maas/', get_combo_view(), name='combo-maas'),
    url(
        r'^raphael/',
        get_combo_view(location=django_settings.RAPHAELJS_LOCATION),
        name='combo-raphael'),
    url(
        r'^yui/',
        get_combo_view(location=django_settings.YUI_LOCATION),
        name='combo-yui'),
)
