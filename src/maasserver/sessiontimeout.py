""" Custom sessionstore for a user-configurable session timeout. """

from django.contrib.sessions.backends.db import SessionStore as DBStore

from maasserver.models import Config


def _get_timeout() -> int:
    timeout = Config.objects.get_config("session_length")
    return timeout


class SessionStore(DBStore):
    def get_session_cookie_age(self) -> int:
        return _get_timeout()
