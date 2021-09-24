from maasserver.models import Config, RegionController
from provisioningserver.certificates import (
    generate_certificate as low_level_generate_certificate,
)
from provisioningserver.certificates import Certificate


def get_maas_client_cn(object_name):
    """Get a CN suitable for a client certificate.

    If the certificate is for a model object, like a Pod, the name of
    the object should be passed in, and the CN will look like
    '$maas_name@object_name'

    If the client certificate isn't tied to a specific object, None can
    be passed in, which will result in the CN beeing the MAAS name.
    """
    maas_name = Config.objects.get_config("maas_name")
    return f"{object_name}@{maas_name}" if object_name else maas_name


def generate_certificate(cn) -> Certificate:
    """Generate an X509 certificate with an RSA private key.

    Set O and OU so that we can identify that a certificate was
    created from this MAAS deployment.
    """
    return low_level_generate_certificate(
        cn,
        organization_name="MAAS",
        organizational_unit_name=RegionController.objects.get_or_create_uuid(),
    )
