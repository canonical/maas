# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.requests.boot_source_selections import (
    BootSourceSelectionRequest,
)
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.utils.date import utcnow


class TestBootSourceSelectionRequest:
    def test_to_builder(self):
        created_at = updated_at = utcnow().astimezone()
        boot_source = BootSource(
            id=1,
            created=created_at,
            updated=updated_at,
            url="http://example.com",
            keyring_filename="/path/to/keyring.gpg",
            keyring_data=b"",
            priority=100,
            skip_keyring_verification=False,
        )
        bootsourceselection_request = BootSourceSelectionRequest(
            os="ubuntu",
            release="noble",
            arch="amd64",
        )
        builder = bootsourceselection_request.to_builder(boot_source)

        assert builder.os == "ubuntu"
        assert builder.release == "noble"
        assert builder.arch == "amd64"
