# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test generation of commissioning user data."""

__all__ = []

import base64
import email

from maasserver.preseed import get_preseed_context
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledWith
from metadataserver.user_data import utils
from metadataserver.user_data.commissioning import generate_user_data
from mock import Mock
from testtools.matchers import ContainsAll


class TestCommissioningUserData(MAASServerTestCase):

    def test_generate_user_data_produces_commissioning_script(self):
        # generate_user_data produces a commissioning script which contains
        # both definitions and use of various commands in python.
        node = factory.make_Node()
        user_data = generate_user_data(node)
        parsed_data = email.message_from_string(user_data.decode("utf-8"))
        self.assertTrue(parsed_data.is_multipart())

        cloud_config = parsed_data.get_payload()[0]
        self.assertEquals(
            'text/cloud-config; charset="utf-8"', cloud_config['Content-Type'])
        self.assertEquals(
            'base64', cloud_config['Content-Transfer-Encoding'])
        self.assertEquals(
            'attachment; filename="config"',
            cloud_config['Content-Disposition'])

        user_data_script = parsed_data.get_payload()[1]
        self.assertEquals(
            'text/x-shellscript; charset="utf-8"',
            user_data_script['Content-Type'])
        self.assertEquals(
            'base64', user_data_script['Content-Transfer-Encoding'])
        self.assertEquals(
            'attachment; filename="user_data.sh"',
            user_data_script['Content-Disposition'])
        self.assertThat(
            base64.b64decode(user_data_script.get_payload()), ContainsAll({
                b'maas-get',
                b'maas-signal',
                b'maas-ipmi-autodetect',
                b'def authenticate_headers',
                b'def encode_multipart_data',
            }))

    def test_nodegroup_passed_to_get_preseed_context(self):
        # I don't care about what effect it has, I just want to know
        # that it was passed as it can affect the contents of
        # `server_host` in the context.
        utils.get_preseed_context = Mock(
            # Use the real return value as it contains data necessary to
            # render the template.
            return_value=get_preseed_context())
        node = factory.make_Node()
        generate_user_data(node)
        self.assertThat(
            utils.get_preseed_context,
            MockCalledWith(nodegroup=node.nodegroup))
