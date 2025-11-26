# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasapiserver.v3.api.public.models.requests.boot_source_selections import (
    BootSourceSelectionFilterParams,
    BootSourceSelectionRequest,
)
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionStatusClauseFactory,
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


class TestBootSourceSelectionFilterParams:
    @pytest.mark.parametrize(
        "ids,selected,expected",
        [
            (
                [1, 2, 3],
                None,
                BootSourceSelectionStatusClauseFactory.with_ids([1, 2, 3]),
            ),
            (
                None,
                True,
                BootSourceSelectionStatusClauseFactory.with_selected(True),
            ),
            (
                None,
                False,
                BootSourceSelectionStatusClauseFactory.with_selected(False),
            ),
            (
                [4, 5],
                True,
                BootSourceSelectionStatusClauseFactory.and_clauses(
                    [
                        BootSourceSelectionStatusClauseFactory.with_ids(
                            [4, 5]
                        ),
                        BootSourceSelectionStatusClauseFactory.with_selected(
                            True
                        ),
                    ]
                ),
            ),
        ],
    )
    def test_to_clause(self, ids, selected, expected):
        filters = BootSourceSelectionFilterParams(ids=ids, selected=selected)
        clause = filters.to_clause()
        assert clause is not None
        assert clause == expected

    @pytest.mark.parametrize(
        "ids,selected,expected",
        [
            (
                [1, 2, 3],
                None,
                "id=1&id=2&id=3",
            ),
            (
                None,
                True,
                "selected=true",
            ),
            (
                None,
                False,
                "selected=false",
            ),
            (
                [4, 5],
                True,
                "id=4&id=5&selected=true",
            ),
        ],
    )
    def test_to_href_format(self, ids, selected, expected):
        filters = BootSourceSelectionFilterParams(ids=ids, selected=selected)
        href = filters.to_href_format()
        assert href == expected
