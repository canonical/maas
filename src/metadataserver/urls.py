# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API URLs."""

from __future__ import (
    absolute_import,
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
from maasserver.api_auth import api_auth
from metadataserver.api import (
    IndexHandler,
    MetaDataHandler,
    UserDataHandler,
    VersionIndexHandler,
    )
from piston.resource import Resource

# Handlers for nodes requesting their own metadata.
meta_data_handler = Resource(MetaDataHandler, authentication=api_auth)
user_data_handler = Resource(UserDataHandler, authentication=api_auth)
version_index_handler = Resource(VersionIndexHandler, authentication=api_auth)
index_handler = Resource(IndexHandler, authentication=api_auth)


# Handlers for anonymous random metadata access.
meta_data_by_mac_handler = Resource(MetaDataHandler)
user_data_by_mac_handler = Resource(UserDataHandler)
version_index_by_mac_handler = Resource(VersionIndexHandler)


# Normal metadata access, available to a node querying its own metadata.
node_patterns = patterns(
    '',
    url(
        r'(?P<version>[^/]+)/meta-data/(?P<item>.*)$',
        meta_data_handler,
        name='metadata-meta-data'),
    url(
        r'(?P<version>[^/]+)/user-data$', user_data_handler,
        name='metadata-user-data'),
    url(
        r'(?P<version>[^/]+)/', version_index_handler,
        name='metadata-version'),
    url(r'', index_handler, name='metadata'),
    )


# Anonymous random metadata access keyed by MAC address.  These won't
# work unless ALLOW_ANONYMOUS_METADATA_ACCESS is enabled, which you
# should never do on a production MAAS.
by_mac_patterns = patterns(
    '',
    url(
        r'(?P<version>[^/]+)/by-mac/(?P<mac>[^/]+)/meta-data/(?P<item>.*)$',
        meta_data_by_mac_handler,
        name='metadata-meta-data-by-mac'),
    url(
        r'(?P<version>[^/]+)/by-mac/(?P<mac>[^/]+)/user-data$',
        user_data_by_mac_handler,
        name='metadata-user-data-by-mac'),
    url(
        r'(?P<version>[^/]+)/by-mac/(?P<mac>[^/]+)/',
        version_index_by_mac_handler,
        name='metadata-version-by-mac'),
    )


# URL patterns.  The anonymous patterns are listed first because they're
# so recognizable: there's no chance of a regular metadata access being
# mistaken for one of these based on URL pattern match.
urlpatterns = by_mac_patterns + node_patterns
