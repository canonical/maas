from django.urls import re_path

from piston3.authentication import (
    HttpBasicAuthentication,
    HttpBasicSimple,
    NoAuthentication,
    oauth_access_token,
    oauth_request_token,
    oauth_user_auth,
)
from piston3.resource import Resource
from test_project.apps.testapp.handlers import (
    AbstractHandler,
    CircularAHandler,
    ConditionalFieldsHandler,
    EchoHandler,
    EntryHandler,
    ExpressiveHandler,
    FileUploadHandler,
    Issue58Handler,
    ListFieldsHandler,
    PlainOldObjectHandler,
)

auth = HttpBasicAuthentication(realm="TestApplication")
noauth = NoAuthentication()

entries = Resource(handler=EntryHandler, authentication=auth)
expressive = Resource(handler=ExpressiveHandler, authentication=auth)
abstract = Resource(handler=AbstractHandler, authentication=auth)
echo = Resource(handler=EchoHandler)
popo = Resource(handler=PlainOldObjectHandler)
list_fields = Resource(handler=ListFieldsHandler)
issue58 = Resource(handler=Issue58Handler)
conditional = Resource(
    handler=ConditionalFieldsHandler, authentication=[auth, noauth]
)
fileupload = Resource(handler=FileUploadHandler)
circular_a = Resource(handler=CircularAHandler)

AUTHENTICATORS = [
    auth,
]
SIMPLE_USERS = (
    ("admin", "secr3t"),
    ("admin", "user"),
    ("admin", "allwork"),
    ("admin", "thisisneat"),
)


class LazyHttpBasicSimple:
    """
    Load HttpBasicSimple instances lazily.

    Django 1.8 ignored exceptions when HttpBasicSimple constructor attempted
    to do User.objects.get() when loading urls.py. Django 1.11 falls over.
    """

    def __init__(self, realm, username, password):
        self.realm = realm
        self.username = username
        self.password = password

        self.instance = None

    def __getattr__(self, name):
        if self.instance is None:
            self.instance = HttpBasicSimple(
                realm=self.realm,
                username=self.username,
                password=self.password,
            )
        return getattr(self.instance, name)


for username, password in SIMPLE_USERS:
    AUTHENTICATORS.append(
        LazyHttpBasicSimple(realm="Test", username=username, password=password)
    )

multiauth = Resource(
    handler=PlainOldObjectHandler, authentication=AUTHENTICATORS
)

urlpatterns = [
    re_path(r"^entries/$", entries),
    re_path(r"^entries/(?P<pk>.+)/$", entries, name="entry"),
    re_path(r"^entries\.(?P<emitter_format>.+)", entries),
    re_path(r"^entry-(?P<pk>.+)\.(?P<emitter_format>.+)", entries),
    re_path(r"^issue58\.(?P<emitter_format>.+)$", issue58),
    re_path(r"^expressive\.(?P<emitter_format>.+)$", expressive),
    re_path(r"^abstract\.(?P<emitter_format>.+)$", abstract),
    re_path(r"^abstract/(?P<id_>\d+)\.(?P<emitter_format>.+)$", abstract),
    re_path(r"^echo$", echo),
    re_path(r"^file_upload/$", fileupload, name="file-upload-test"),
    re_path(r"^multiauth/$", multiauth),
    re_path(r"^circular_a/$", circular_a),
    # oauth entrypoints
    re_path(r"^oauth/request_token$", oauth_request_token),
    re_path(r"^oauth/authorize$", oauth_user_auth),
    re_path(r"^oauth/access_token$", oauth_access_token),
    re_path(r"^list_fields$", list_fields),
    re_path(r"^list_fields/(?P<id>.+)$", list_fields),
    re_path(r"^popo$", popo),
    re_path(r"^conditional_fields$", conditional, name="conditional-list"),
    re_path(
        r"^conditional_fields/(?P<object_id>\d+)$",
        conditional,
        name="conditional-detail",
    ),
]
