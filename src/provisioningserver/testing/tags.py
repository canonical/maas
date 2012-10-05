# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from apiclient.testing.django_client_proxy import MAASDjangoTestClient
from fixtures import Fixture
from maasserver.models import NodeGroup
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.utils.orm import get_one
from maasserver.worker_user import get_worker_user
from provisioningserver import tags
from testtools.monkey import patch


def get_nodegroup_cached_knowledge():
    """Get a MAASClient and nodegroup_uuid.

    We make use of the fact that populate_tags refreshes the secrets before it
    starts doing work. So effectively the single real-world worker changes
    workers on each iteration of the loop.

    The MAASDjangoTestClient that is returned proxies to the Django testing
    Client, so we don't actually have to make HTTP calls.
    """
    nodegroup_uuid = tags.get_recorded_nodegroup_uuid()
    maas_client = get_nodegroup_worker_client(nodegroup_uuid)
    return maas_client, nodegroup_uuid


def get_nodegroup_worker_client(nodegroup_uuid):
    """Get a MAASClient that can do work for this nodegroup."""
    nodegroup = get_one(NodeGroup.objects.filter(uuid=nodegroup_uuid))
    django_client = OAuthAuthenticatedClient(
        get_worker_user(), token=nodegroup.api_token)
    maas_client = MAASDjangoTestClient(django_client)
    return maas_client


class TagCachedKnowledgeFixture(Fixture):
    """Install the get_nodegroup_cached_knowledge for this test."""

    def setUp(self):
        super(TagCachedKnowledgeFixture, self).setUp()
        restore = patch(
            tags, "get_cached_knowledge", get_nodegroup_cached_knowledge)
        self.addCleanup(restore)
