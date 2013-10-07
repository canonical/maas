# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test generation of commissioning user data."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import ContainsAll
from metadataserver.commissioning import user_data
from metadataserver.commissioning.user_data import generate_user_data
from mock import (
    Mock,
    sentinel,
    )


class TestUserData(MAASServerTestCase):

    def test_generate_user_data_produces_commissioning_script(self):
        # generate_user_data produces a commissioning script which contains
        # both definitions and use of various commands in python.
        self.assertThat(
            generate_user_data(), ContainsAll({
                'maas-get',
                'maas-signal',
                'maas-ipmi-autodetect',
                'def authenticate_headers',
                'def encode_multipart_data',
            }))

    def test_nodegroup_passed_to_get_preseed_context(self):
        # I don't care about what effect it has, I just want to know
        # that it was passed as it can affect the contents of
        # `server_host` in the context.
        fake_context = dict(http_proxy=factory.getRandomString())
        user_data.get_preseed_context = Mock(return_value=fake_context)
        nodegroup = sentinel.nodegroup
        generate_user_data(nodegroup)
        user_data.get_preseed_context.assert_called_with(nodegroup=nodegroup)

    def test_generate_user_data_generates_mime_multipart(self):
        # The generate_user_data func should create a MIME multipart
        # message consisting of cloud-config and x-shellscript
        # attachments.
        self.assertThat(
            generate_user_data(), ContainsAll({
                'multipart',
                'Content-Type: text/cloud-config',
                'Content-Type: text/x-shellscript',
            }))
