# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL configuration for the maas project."""


from django.conf.urls import include, url

urlpatterns = [
    url(r"^", include("maasserver.urls")),
    url(r"^metadata/", include("metadataserver.urls")),
]
