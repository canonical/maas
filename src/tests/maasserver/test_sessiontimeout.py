# Copyright 2023-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasserver.models import Config
from maasserver.sessiontimeout import SessionStore
from maasserver.websockets.handlers.config import ConfigHandler


@pytest.mark.usefixtures("mock_openfga")
class TestSessionTimeout:
    def test_default_config(self, factory):
        admin = factory.make_admin()
        handler = ConfigHandler(admin, {}, None)
        config = {"name": "session_length", "value": 1209600}
        handler_config = handler.get({"name": "session_length"})
        assert config == handler_config

    def test_default_cookie_age(self, factory):
        admin = factory.make_admin()
        handler = ConfigHandler(admin, {}, None)
        sess = SessionStore()
        value = sess.get_session_cookie_age()
        config = {"name": "session_length", "value": value}
        handler_config = handler.get({"name": "session_length"})
        assert config == handler_config

    def test_update_cookie_age(self, factory):
        admin = factory.make_admin()
        handler = ConfigHandler(admin, {}, None)
        sess = SessionStore()
        handler.update({"name": "session_length", "value": 50})
        value = sess.get_session_cookie_age()
        config = {"name": "session_length", "value": value}
        handler_config = handler.get({"name": "session_length"})
        assert config == handler_config


class TestSessionLengthConfig:
    def test_changing_session_length_deletes_sessions(self, maasdb):
        SessionStore().create()
        SessionStore().create()
        Config.objects.set_config("session_length", 300)
        assert SessionStore.get_model_class().objects.count() == 0
