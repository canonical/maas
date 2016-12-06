# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL configuration for the maas project."""

__all__ = []

from django.conf import settings
from django.conf.urls import (
    include,
    patterns,
    url,
)
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = patterns(
    '',
    url(r'^', include('maasserver.urls')),
    url(r'^metadata/', include('metadataserver.urls')),
)

if settings.STATIC_LOCAL_SERVE:
    urlpatterns += patterns(
        '',
        (r'^media/(?P<path>.*)$', 'django.views.static.serve',
         {'document_root': settings.MEDIA_ROOT}),
    )

    urlpatterns += staticfiles_urlpatterns(settings.STATIC_URL_PATTERN)
