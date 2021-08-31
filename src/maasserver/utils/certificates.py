from maasserver.models import Config


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
