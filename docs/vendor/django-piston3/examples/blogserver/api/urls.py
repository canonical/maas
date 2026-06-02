from django.conf.urls import patterns
from django.urls import re_path

from blogserver.api.handlers import BlogpostHandler
from piston3.authentication import HttpBasicAuthentication
from piston3.doc import documentation_view
from piston3.resource import Resource

auth = HttpBasicAuthentication(realm="My sample API")

blogposts = Resource(handler=BlogpostHandler, authentication=auth)

urlpatterns = patterns(
    "",
    re_path(r"^posts/$", blogposts),
    re_path(r"^posts/(?P<emitter_format>.+)/$", blogposts),
    re_path(r"^posts\.(?P<emitter_format>.+)", blogposts, name="blogposts"),
    # automated documentation
    re_path(r"^$", documentation_view),
)
