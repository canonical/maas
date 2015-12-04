# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL combo routing configuration."""

__all__ = []


from django.conf import settings
from django.conf.urls import (
    patterns,
    url,
)
from maasserver.views.combo import (
    get_combo_view,
    merge_view,
)


urlpatterns = patterns(
    '',
    url(
        r'^yui/',
        get_combo_view(location=settings.YUI_LOCATION),
        name='combo-yui'),
    url(
        r'^(?P<filename>[^/]*)', merge_view, name='merge'),
)
