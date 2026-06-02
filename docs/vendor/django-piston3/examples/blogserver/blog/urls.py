from django.conf.urls import patterns
from django.url import re_path

urlpatterns = patterns(
    "blogserver.blog.views",
    re_path(r"^$", "posts", name="posts"),
    re_path(r"^js$", "test_js"),
)
