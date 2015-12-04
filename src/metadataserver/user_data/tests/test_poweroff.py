# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test generation of poweroff user data."""

__all__ = []

import base64
import email

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.user_data.poweroff import generate_user_data
from testtools.matchers import ContainsAll


class TestPoweroffUserData(MAASServerTestCase):

    def test_generate_user_data_produces_poweroff_script(self):
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
                b'Powering node off',
                b'poweroff',
            }))
