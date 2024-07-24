#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Request


def extract_absolute_uri(request: Request) -> str:
    if (
        "x-forwarded-host" in request.headers
        and "x-forwarded-proto" in request.headers
    ):
        return f"{request.headers.get('x-forwarded-proto')}://{request.headers.get('x-forwarded-host')}/"
    return str(request.base_url)
