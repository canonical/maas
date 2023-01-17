# Tests for custom sessionbase to configure timeout

from maasserver.sessiontimeout import SessionStore
from maasserver.websockets.handlers.config import ConfigHandler


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
