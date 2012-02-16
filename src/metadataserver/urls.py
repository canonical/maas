# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API URLs."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'urlpatterns',
    ]

from django.conf.urls.defaults import (
    patterns,
    url,
    )
from metadataserver.api import (
    meta_data,
    metadata_index,
    user_data,
    version_index,
    )


urlpatterns = patterns(
    '',
    url(
        r'(?P<version>[^/]+)/meta-data/(?P<item>.*)$', meta_data,
        name='metadata_meta_data'),
    url(
        r'(?P<version>[^/]+)/user-data$', user_data,
        name='metadata_user_data'),
    url(r'(?P<version>[^/]+)/', version_index, name='metadata_version'),
    url(r'', metadata_index, name='metadata'),
    )
