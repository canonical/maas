# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test generation of disk erasing user data."""

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
from metadataserver.user_data.disk_erasing import generate_user_data
from testtools.matchers import ContainsAll


class TestDiskErasingUserData(MAASServerTestCase):

    def test_generate_user_data_produces_disk_erase_script(self):
        node = factory.make_Node()
        user_data = generate_user_data(node)
        # On Vivid and above the email library defaults to encoding the MIME
        # data as base64. We only check the inner contents if its not base64.
        if "Content-Transfer-Encoding: base64" not in user_data:
            self.assertThat(
                user_data, ContainsAll({
                    'config',
                    'user_data.sh',
                    'maas-signal',
                    'erase_disks',
                    'def authenticate_headers',
                    'def encode_multipart_data',
                }))
        else:
            self.assertThat(
                user_data, ContainsAll({
                    'config',
                    'user_data.sh',
                }))
