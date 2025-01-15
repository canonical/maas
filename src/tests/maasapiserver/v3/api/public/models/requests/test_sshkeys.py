# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.sshkeys import (
    SshKeyImportFromSourceRequest,
    SshKeyManualUploadRequest,
)


class TestSshKeyImportFromSourceRequest:
    def test_mandatory_params(self):
        with pytest.raises(ValidationError) as e:
            SshKeyImportFromSourceRequest()

        assert len(e.value.errors()) == 2
        assert {"protocol", "auth_id"} == set(
            [f["loc"][0] for f in e.value.errors()]
        )


class TestSshKeyManualUploadRequest:
    def test_mandatory_params(self):
        with pytest.raises(ValidationError) as e:
            SshKeyManualUploadRequest()

        assert len(e.value.errors()) == 1
        assert {"key"} == set([f["loc"][0] for f in e.value.errors()])
