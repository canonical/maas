# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL combo routing configuration."""

__all__ = []


from django.conf.urls import url
from maasserver.views.combo import merge_view


urlpatterns = [url(r"^(?P<filename>[^/]*)", merge_view, name="merge")]
