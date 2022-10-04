# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client

from django.urls import reverse

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.testing.certificates import get_sample_cert


class TestVMHostCertificateHandler(MAASServerTestCase):
    def test_certificate_pem(self):
        cert = get_sample_cert()
        name = factory.make_name()
        factory.make_Pod(
            name=name,
            pod_type="lxd",
            parameters={
                "power_address": "1.2.3.4",
                "certificate": cert.certificate_pem(),
                "key": cert.private_key_pem(),
            },
        )
        response = self.client.get(reverse("vmhost-certificate", args=[name]))
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(response.content.decode(), cert.certificate_pem())

    def test_no_cert(self):
        name = factory.make_name()
        factory.make_Pod(
            name=name,
            pod_type="lxd",
            parameters={
                "power_address": "1.2.3.4",
                "password": "sekret",
            },
        )
        response = self.client.get(reverse("vmhost-certificate", args=[name]))
        self.assertEqual(response.status_code, http.client.NOT_FOUND)

    def test_no_vmhost(self):
        response = self.client.get(
            reverse("vmhost-certificate", args=["not-here"])
        )
        self.assertEqual(response.status_code, http.client.NOT_FOUND)
