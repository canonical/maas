# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.boot_source_selections import (
    BootSourceSelectionRequest,
    BootSourceSelectionStatisticFilterParams,
    BootSourceSelectionStatusFilterParams,
    BulkSelectionRequest,
    SelectionRequest,
)
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
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


class TestSelectionRequest:
    def test_to_builder(self):
        selection_request = SelectionRequest(
            os="ubuntu", release="noble", arch="amd64", boot_source_id=1
        )
        builder = selection_request.to_builder()

        assert builder.os == "ubuntu"
        assert builder.release == "noble"
        assert builder.arch == "amd64"
        assert builder.boot_source_id == 1


class TestBulkSelectionRequest:
    def test_selection_constraints__min_length(self):
        with pytest.raises(ValidationError):
            BulkSelectionRequest(selections=[])

    def test_selection_constraints__unique(self):
        selection_request = SelectionRequest(
            os="ubuntu", release="noble", arch="amd64", boot_source_id=1
        )
        with pytest.raises(ValidationError):
            BulkSelectionRequest(
                selections=[selection_request, selection_request]
            )

    def test_get_builders(self):
        selection_request = SelectionRequest(
            os="ubuntu", release="noble", arch="amd64", boot_source_id=1
        )
        bulk_selection_request = BulkSelectionRequest(
            selections=[selection_request]
        )
        builders = bulk_selection_request.get_builders()

        assert len(builders) == 1


class TestBootSourceSelectionStatusFilterParams:
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
        filters = BootSourceSelectionStatusFilterParams(
            ids=ids, selected=selected
        )
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
        filters = BootSourceSelectionStatusFilterParams(
            ids=ids, selected=selected
        )
        href = filters.to_href_format()
        assert href == expected


class TestBootSourceSelectionStatisticFilterParams:
    @pytest.mark.parametrize(
        "ids,expected",
        [
            (None, None),
            ([1], BootSourceSelectionClauseFactory.with_ids([1])),
            ([1, 2, 3], BootSourceSelectionClauseFactory.with_ids([1, 2, 3])),
        ],
    )
    def test_to_clause(self, ids, expected):
        filters = BootSourceSelectionStatisticFilterParams(ids=ids)
        clause = filters.to_clause()
        assert clause == expected

    @pytest.mark.parametrize(
        "ids,expected",
        [(None, None), ([1], "id=1"), ([1, 2, 3], "id=1&id=2&id=3")],
    )
    def test_to_href_format(self, ids, expected):
        filters = BootSourceSelectionStatisticFilterParams(ids=ids)
        href = filters.to_href_format()
        assert href == expected
