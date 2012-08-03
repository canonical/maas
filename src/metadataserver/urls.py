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
    AnonMetaDataHandler,
    EnlistMetaDataHandler,
    EnlistUserDataHandler,
    EnlistVersionIndexHandler,
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


# Handlers for anonymous metadata operations.
meta_data_anon_handler = Resource(AnonMetaDataHandler)


# Handlers for UNSAFE anonymous random metadata access.
meta_data_by_mac_handler = Resource(MetaDataHandler)
user_data_by_mac_handler = Resource(UserDataHandler)
version_index_by_mac_handler = Resource(VersionIndexHandler)

# Handlers for the anonymous enlistment metadata service
enlist_meta_data_handler = Resource(EnlistMetaDataHandler)
enlist_user_data_handler = Resource(EnlistUserDataHandler)
enlist_index_handler = Resource(IndexHandler)
enlist_version_index_handler = Resource(EnlistVersionIndexHandler)

# Normal metadata access, available to a node querying its own metadata.
node_patterns = patterns(
    '',
    url(
        # could-init adds additional slashes in front of urls.
        r'^/*(?P<version>[^/]+)/meta-data/(?P<item>.*)$',
        meta_data_handler,
        name='metadata-meta-data'),
    url(
        # could-init adds additional slashes in front of urls.
        r'^/*(?P<version>[^/]+)/user-data$', user_data_handler,
        name='metadata-user-data'),
    url(
        # could-init adds additional slashes in front of urls.
        r'^/*(?P<version>[^/]+)/', version_index_handler,
        name='metadata-version'),
    url(
        # could-init adds additional slashes in front of urls.
        r'^/*', index_handler, name='metadata'),
    )

# Anonymous random metadata access, keyed by system ID.  These serve requests
# from the nodes which happen when the environment is so minimal that proper
# authenticated calls are not possible.
by_id_patterns = patterns(
    '',
    # XXX: rvb 2012-06-20 bug=1015559:  This method is accessible
    # without authentication.  This is a security threat.
    url(
        # could-init adds additional slashes in front of urls.
        r'^/*(?P<version>[^/]+)/by-id/(?P<system_id>[\w\-]+)/$',
        meta_data_anon_handler,
        name='metadata-node-by-id'),
    url(
        # could-init adds additional slashes in front of urls.
        r'^/*(?P<version>[^/]+)/enlist-preseed/$',
        meta_data_anon_handler,
        name='metadata-enlist-preseed'),
    )

# UNSAFE anonymous random metadata access, keyed by MAC address.  These won't
# work unless ALLOW_UNSAFE_METADATA_ACCESS is enabled, which you should never
# do on a production MAAS.
by_mac_patterns = patterns(
    '',
    url(
        # could-init adds additional slashes in front of urls.
        r'^/*(?P<version>[^/]+)/by-mac/(?P<mac>[^/]+)/meta-data/(?P<item>.*)$',
        meta_data_by_mac_handler,
        name='metadata-meta-data-by-mac'),
    url(
        # could-init adds additional slashes in front of urls.
        r'^/*(?P<version>[^/]+)/by-mac/(?P<mac>[^/]+)/user-data$',
        user_data_by_mac_handler,
        name='metadata-user-data-by-mac'),
    url(
        # could-init adds additional slashes in front of urls.
        r'^/*(?P<version>[^/]+)/by-mac/(?P<mac>[^/]+)/',
        version_index_by_mac_handler,
        name='metadata-version-by-mac'),
    )

# Anonymous enlistment entry point
enlist_metadata_patterns = patterns(
    '',
    url(
        r'^/*enlist/(?P<version>[^/]+)/meta-data/(?P<item>.*)$',
        enlist_meta_data_handler,
        name='enlist-metadata-meta-data'),
    url(
        r'^/*enlist/(?P<version>[^/]+)/user-data$', enlist_user_data_handler,
        name='enlist-metadata-user-data'),
    url(
        r'^/*enlist/(?P<version>[^/]+)[/]*$', enlist_version_index_handler,
        name='enlist-version'),
    url(r'^/*enlist[/]*$', enlist_index_handler, name='enlist'),
    )


# URL patterns.  The anonymous patterns are listed first because they're
# so recognizable: there's no chance of a regular metadata access being
# mistaken for one of these based on URL pattern match.
urlpatterns = (
    enlist_metadata_patterns + by_id_patterns + by_mac_patterns +
    node_patterns)
