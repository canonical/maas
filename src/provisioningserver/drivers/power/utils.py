# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for MAAS power drivers."""


from twisted.internet._sslverify import (
    ClientTLSOptions,
    OpenSSLCertificateOptions,
)
from twisted.web.client import BrowserLikePolicyForHTTPS


class WebClientContextFactory(BrowserLikePolicyForHTTPS):
    def creatorForNetloc(self, hostname, port):
        opts = ClientTLSOptions(
            hostname.decode("ascii"),
            OpenSSLCertificateOptions(verify=False).getContext(),
        )
        # This forces Twisted to not validate the hostname of the certificate.
        opts._ctx.set_info_callback(lambda *args: None)
        return opts
