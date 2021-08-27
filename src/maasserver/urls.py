# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL routing configuration."""


from django.conf.urls import include, url
from django.http import HttpResponse
from django.views.generic import TemplateView

from maasserver import urls_api
from maasserver.bootresources import (
    simplestreams_file_handler,
    simplestreams_stream_handler,
)
from maasserver.macaroon_auth import MacaroonDischargeRequest
from maasserver.prometheus.stats import prometheus_stats_handler
from maasserver.views.account import authenticate, csrf, login, logout
from maasserver.views.rpc import info
from maasserver.views.vmhost import vmhost_certificate_handler

# Anonymous views.
urlpatterns = [
    url(r"^accounts/login/$", login, name="login"),
    url(r"^accounts/authenticate/$", authenticate, name="authenticate"),
    url(
        r"^accounts/discharge-request/$",
        MacaroonDischargeRequest(),
        name="discharge-request",
    ),
    url(
        r"^images-stream/streams/v1/(?P<filename>.*)$",
        simplestreams_stream_handler,
        name="simplestreams_stream_handler",
    ),
    url(
        r"^images-stream/(?P<os>.*)/(?P<arch>.*)/(?P<subarch>.*)/"
        "(?P<series>.*)/(?P<version>.*)/(?P<filename>.*)$",
        simplestreams_file_handler,
        name="simplestreams_file_handler",
    ),
    url(
        r"^maas-run-scripts$",
        TemplateView.as_view(
            template_name="maas_run_scripts.template",
            content_type="text/x-python",
        ),
        name="maas-run-scripts",
    ),
    url(r"^metrics$", prometheus_stats_handler, name="metrics"),
    url(
        r"^robots\.txt$",
        TemplateView.as_view(
            template_name="robots.txt", content_type="text/plain"
        ),
        name="robots",
    ),
    url(
        r"^vmhost-certificate/(?P<name>[^/]+)$",
        vmhost_certificate_handler,
        name="vmhost-certificate",
    ),
]

# # URLs for logged-in users.
# Preferences views.
urlpatterns += [url(r"^account/csrf/$", csrf, name="csrf")]
# Logout view.
urlpatterns += [url(r"^accounts/logout/$", logout, name="logout")]

# API URLs. If old API requested, provide error message directing to new API.
urlpatterns += [
    url(r"^api/2\.0/", include(urls_api)),
    url(
        r"^api/version/",
        lambda request: HttpResponse(content="2.0", content_type="text/plain"),
        name="api_version",
    ),
    url(
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
urlpatterns += [url(r"^rpc/$", info, name="rpc-info")]
