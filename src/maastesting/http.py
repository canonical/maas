# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for http."""

from django.http.request import HttpRequest


def make_HttpRequest(server_name=None, server_port=None, http_host=None):
    if server_name is None:
        server_name = "testserver"
    if server_port is None:
        server_port = 80
    request = HttpRequest()
    request.META["SERVER_NAME"] = server_name
    request.META["SERVER_PORT"] = server_port
    if http_host is not None:
        request.META["HTTP_HOST"] = http_host
    return request
