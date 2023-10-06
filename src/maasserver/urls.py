# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL routing configuration."""


from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import TemplateView

from maasserver import urls_api
from maasserver.api.doc_oapi import landing_page
from maasserver.bootresources import (
    simplestreams_file_handler,
    simplestreams_stream_handler,
)
from maasserver.macaroon_auth import MacaroonDischargeRequest
from maasserver.prometheus.service import prometheus_discovery_handler
from maasserver.prometheus.stats import prometheus_stats_handler
from maasserver.views.account import authenticate, csrf, login, logout
from maasserver.views.rpc import info
from maasserver.views.vmhost import vmhost_certificate_handler

# Anonymous views.
urlpatterns = [
    path("accounts/login/", login, name="login"),
    path("accounts/authenticate/", authenticate, name="authenticate"),
    path(
        "accounts/discharge-request/",
        MacaroonDischargeRequest(),
        name="discharge-request",
    ),
    re_path(
        r"^images-stream/streams/v1/(?P<filename>.*)$",
        simplestreams_stream_handler,
        name="simplestreams_stream_handler",
    ),
    re_path(
        r"^images-stream/(?P<os>.*)/(?P<arch>.*)/(?P<subarch>.*)/"
        "(?P<series>.*)/(?P<version>.*)/(?P<filename>.*)$",
        simplestreams_file_handler,
        name="simplestreams_file_handler",
    ),
    path(
        "maas-run-scripts",
        TemplateView.as_view(
            template_name="maas_run_scripts.template",
            content_type="text/x-python",
        ),
        name="maas-run-scripts",
    ),
    path("metrics", prometheus_stats_handler, name="metrics"),
    path(
        "metrics/endpoints",
        prometheus_discovery_handler,
        name="metrics_endpoints",
    ),
    re_path(
        r"^robots\.txt$",
        TemplateView.as_view(
            template_name="robots.txt", content_type="text/plain"
        ),
        name="robots",
    ),
    path(
        "vmhost-certificate/<str:name>",
        vmhost_certificate_handler,
        name="vmhost-certificate",
    ),
]

# # URLs for logged-in users.
# Preferences views.
urlpatterns += [path("account/csrf/", csrf, name="csrf")]
# Logout view.
urlpatterns += [path("accounts/logout/", logout, name="logout")]

# API URLs. If old API requested, provide error message directing to new API.
urlpatterns += [
    path("api/", landing_page),
    re_path(r"^api/docs/", TemplateView.as_view(template_name="openapi.html")),
    re_path(r"^api/2\.0/", include(urls_api)),
    re_path(
        r"^api/version/",
        lambda request: HttpResponse(content="2.0", content_type="text/plain"),
        name="api_version",
    ),
    re_path(
        r"^api/1.0/",
        lambda request: HttpResponse(
            content_type="text/plain",
            status=410,
            content="The 1.0 API is no longer available. "
            "Please use API version 2.0.",
        ),
        name="api_v1_error",
    ),
]


# RPC URLs.
urlpatterns += [path("rpc/", info, name="rpc-info")]
