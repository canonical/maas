#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasapiserver.v3.auth.bearer import get_bearer_token


@pytest.mark.parametrize(
    "header, expected",
    [
        ("bearer maas_pat_x", "maas_pat_x"),
        ("Bearer maas_pat_x", "maas_pat_x"),
        ("bearer  maas_pat_x", ""),
        ("Basic maas_pat_x", None),
        ("bearer", None),
        (None, None),
    ],
)
def test_get_bearer_token(header: str | None, expected: str | None) -> None:
    assert get_bearer_token(header) == expected
