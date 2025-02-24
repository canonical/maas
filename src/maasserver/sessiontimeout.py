"""Custom sessionstore for a user-configurable session timeout."""

from django.contrib.sessions.backends.db import SessionStore as DBStore

from maasserver.models import Config
from maasservicelayer.models.configurations import ConfigFactory


class SessionStore(DBStore):
    def get_session_cookie_age(self) -> int:
        return _get_session_length()


def clear_existing_sessions():
    """Clear all existing sessions from the database."""
    SessionStore.get_model_class().objects.all().delete()


def _get_session_length() -> int:
    """Return the session duration."""
    return (
        Config.objects.get_config("session_length")
        or ConfigFactory.get_config_model("session_length").default
    )
