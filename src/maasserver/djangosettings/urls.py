# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL configuration for the maas project."""


from django.urls import include, path

urlpatterns = [
    path("", include("maasserver.urls")),
    path("metadata/", include("metadataserver.urls")),
]
