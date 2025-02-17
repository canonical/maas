#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.domains import DomainRequest


class TestDomainRequest:
    def test_mandatory_params(self) -> None:
        with pytest.raises(ValidationError) as e:
            DomainRequest()
        assert len(e.value.errors()) == 1
        assert "name" in (e.value.errors()[0]["loc"][0])

    @pytest.mark.parametrize(
        "ttl, valid",
        [
            (1, True),
            (604800, True),
            (0, False),
            (604801, False),
        ],
    )
    def test_check_ttl(self, ttl: int, valid: bool) -> None:
        if not valid:
            with pytest.raises(ValidationError):
                DomainRequest(
                    name="name",
                    ttl=ttl,
                )
        else:
            DomainRequest(
                name="name",
                ttl=ttl,
            )

    def test_to_builder(self) -> None:
        dr = DomainRequest(
            name="domain-name",
        )
        b = dr.to_builder()
        assert dr.name == b.name
