# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers for TLS negotiation with AMP."""


from functools import partial

from twisted.internet import ssl
from twisted.python import filepath


def get_tls_parameters(private_cert_name, trust_cert_name):
    """get_tls_parameters()

    Implementation of
    :py:class:`~twisted.protocols.amp.StartTLS`.
    """
    testing = filepath.FilePath(__file__).parent()
    with testing.child(private_cert_name).open() as fin:
        tls_localCertificate = ssl.PrivateCertificate.loadPEM(fin.read())
    with testing.child(trust_cert_name).open() as fin:
        tls_verifyAuthorities = [ssl.Certificate.loadPEM(fin.read())]
    return {
        "tls_localCertificate": tls_localCertificate,
        "tls_verifyAuthorities": tls_verifyAuthorities,
    }


get_tls_parameters_for_cluster = partial(
    get_tls_parameters, "cluster.crt", "trust.crt"
)
get_tls_parameters_for_region = partial(
    get_tls_parameters, "region.crt", "trust.crt"
)
