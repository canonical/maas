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
from maas.api_auth import api_auth
from metadataserver.api import (
    IndexHandler,
    MetaDataHandler,
    UserDataHandler,
    VersionIndexHandler,
    )
from piston.resource import Resource


meta_data_handler = Resource(MetaDataHandler, authentication=api_auth)
user_data_handler = Resource(UserDataHandler, authentication=api_auth)
version_index_handler = Resource(VersionIndexHandler, authentication=api_auth)
index_handler = Resource(IndexHandler, authentication=api_auth)


urlpatterns = patterns(
    '',
    url(
        r'(?P<version>[^/]+)/meta-data/(?P<item>.*)$',
        meta_data_handler,
        name='metadata_meta_data'),
    url(
        r'(?P<version>[^/]+)/user-data$', user_data_handler,
        name='metadata_user_data'),
    url(
        r'(?P<version>[^/]+)/', version_index_handler,
        name='metadata_version'),
    url(r'', index_handler, name='metadata'),
    )
