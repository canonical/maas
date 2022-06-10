# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL configuration for the maas project."""


from django.urls import include, re_path

urlpatterns = [
    re_path(r"^", include("maasserver.urls")),
    re_path(r"^metadata/", include("metadataserver.urls")),
]
