#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from tests.maasapiserver.fixtures.app import SharedMockedApps


def test_shared_app_is_reused_without_previous_services_mock():
    apps = SharedMockedApps()
    first_mock = Mock()
    with apps.bind(first_mock) as first_app:
        assert first_app.state.services_mock is first_mock
    with apps.bind(Mock()) as second_app:
        assert second_app is first_app
        assert second_app.state.services_mock is not first_mock
    assert not hasattr(first_app.state, "services_mock")


def test_modifying_shared_app_fails_and_discards_it():
    apps = SharedMockedApps()
    with pytest.raises(pytest.fail.Exception, match="modified a shared app"):
        with apps.bind(Mock()) as modified_app:
            modified_app.dependency_overrides[object] = object
    with apps.bind(Mock()) as next_app:
        assert next_app is not modified_app
        assert next_app.dependency_overrides == {}
