# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasserver.secrets import SecretManager
from provisioningserver.certificates import Certificate


def get_maas_certificate() -> Optional[Certificate]:
    """Return the TLS certificate for MAAS, or None if TLS is not enabled."""
    secrets = SecretManager().get_composite_secret("tls", default=None)
    if not secrets or not all((secrets.get("key"), secrets.get("cert"))):
        return None
    return Certificate.from_pem(
        secrets["key"],
        secrets["cert"],
        ca_certs_material=secrets.get("cacert", ""),
    )
