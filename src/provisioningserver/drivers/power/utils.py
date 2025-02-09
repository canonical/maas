# Copyright 2019-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for MAAS power drivers."""

from twisted.internet._sslverify import (
    ClientTLSOptions,
    OpenSSLCertificateOptions,
)
from twisted.web.client import BrowserLikePolicyForHTTPS


class WebClientContextFactory(BrowserLikePolicyForHTTPS):
    def __init__(self, verify=False, **kwargs):
        super().__init__(**kwargs)
        self._verify = verify

    def creatorForNetloc(self, hostname, port):
        opts = ClientTLSOptions(
            hostname.decode("ascii"),
            OpenSSLCertificateOptions(verify=self._verify).getContext(),
        )
        # This forces Twisted to not validate the hostname of the certificate.
        opts._ctx.set_info_callback(lambda *args: None)
        return opts
