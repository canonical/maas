# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test generation of disk erasing user data."""

__all__ = []

import base64
import email
import re

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.user_data.disk_erasing import generate_user_data
from testtools.matchers import ContainsAll


class TestDiskErasingUserData(MAASServerTestCase):

    scenarios = (
        ('secure_and_quick', {
            'kwargs': {
                'secure_erase': True,
                'quick_erase': True,
            },
            'maas_wipe': (
                rb'^\s*maas-wipe\s--secure-erase\s--quick-erase$\s*signal\sOK')
        }),
        ('secure_not_quick', {
            'kwargs': {
                'secure_erase': True,
                'quick_erase': False,
            },
            'maas_wipe': rb'^\s*maas-wipe\s--secure-erase\s$\s*signal\sOK'
        }),
        ('quick_not_secure', {
            'kwargs': {
                'secure_erase': False,
                'quick_erase': True,
            },
            'maas_wipe': rb'^\s*maas-wipe\s\s--quick-erase$\s*signal\sOK'
        }),
        ('not_quick_not_secure', {
            'kwargs': {
                'secure_erase': False,
                'quick_erase': False,
            },
            'maas_wipe': rb'^\s*maas-wipe\s\s$\s*signal\sOK'
        }),
    )

    def test_generate_user_data_produces_disk_erase_script(self):
        node = factory.make_Node()
        user_data = generate_user_data(node, **self.kwargs)
        parsed_data = email.message_from_string(user_data.decode("utf-8"))
        self.assertTrue(parsed_data.is_multipart())

        user_data_script = parsed_data.get_payload()[0]
        self.assertEquals(
            'text/x-shellscript; charset="utf-8"',
            user_data_script['Content-Type'])
        self.assertEquals(
            'base64', user_data_script['Content-Transfer-Encoding'])
        self.assertEquals(
            'attachment; filename="user_data.sh"',
            user_data_script['Content-Disposition'])
        payload = base64.b64decode(user_data_script.get_payload())
        self.assertThat(
            payload, ContainsAll({
                b'maas-signal',
                b'def authenticate_headers',
                b'def encode_multipart_data',
            }))
        self.assertIsNotNone(
            re.search(self.maas_wipe, payload, re.MULTILINE | re.DOTALL))
