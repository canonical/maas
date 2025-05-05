# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.notifications import (
    NotificationRequest,
)
from maascommon.enums.notifications import NotificationCategoryEnum


class TestNotificationRequest:
    def test_to_builder(self):
        notification_request = NotificationRequest(
            ident="deprecation_MD5_users",
            message="Foo is deprecated, please update",
            for_users=True,
            for_admins=False,
            context={},
            user_id=None,
            category=NotificationCategoryEnum.WARNING,
            dismissable=True,
        )
        builder = notification_request.to_builder()
        assert builder.ident == notification_request.ident
        assert builder.message == notification_request.message
        assert builder.users == notification_request.for_users
        assert builder.admins == notification_request.for_admins
        assert builder.context == notification_request.context
        assert builder.user_id == notification_request.user_id
        assert builder.category == notification_request.category
        assert builder.dismissable == notification_request.dismissable

    def test_mandatory_params(self):
        with pytest.raises(ValidationError) as e:
            NotificationRequest()

        assert len(e.value.errors()) == 2
        assert "message" in (e.value.errors()[0]["loc"][0])

    def test_missing_recipient(self):
        with pytest.raises(ValidationError) as e:
            NotificationRequest(message="foo")
        assert (
            e.value.errors()[0]["msg"]
            == "Either 'user_id', 'for_users' or 'for_admin' must be specified."
        )
