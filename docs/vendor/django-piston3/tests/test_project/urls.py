from django.conf.urls import include
from django.contrib import admin
from django.urls import re_path

from test_project.apps.testapp import urls as testapp_urls

admin_patterns = re_path("admin/", admin.site.urls)
admin.autodiscover()

urlpatterns = [
    re_path(r"api/", include(testapp_urls)),
    admin_patterns,
]
