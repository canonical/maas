# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL configuration for the maas project."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.conf import settings
from django.conf.urls.defaults import (
    include,
    patterns,
    url,
    )
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = patterns('',
    url(r'^', include('maasserver.urls')),
    url(r'^metadata', include('metadataserver.urls')),
)

if settings.STATIC_LOCAL_SERVE:
    urlpatterns += patterns('',
        (r'^media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.MEDIA_ROOT}),
    )

    urlpatterns += staticfiles_urlpatterns()

if settings.DEBUG:
    from django.contrib import admin
    admin.autodiscover()

    urlpatterns += patterns('',
        (r'^admin/', include(admin.site.urls)),
    )
