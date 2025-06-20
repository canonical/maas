# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Request
from pydantic import BaseModel, IPvAnyAddress, ValidationError


class _IPValidator(BaseModel):
    ip: IPvAnyAddress


def extract_absolute_uri(request: Request) -> str:
    if (
        "x-forwarded-host" in request.headers
        and "x-forwarded-proto" in request.headers
    ):
        return f"{request.headers.get('x-forwarded-proto')}://{request.headers.get('x-forwarded-host')}/"
    return str(request.base_url)


def get_remote_ip(request: Request) -> IPvAnyAddress | None:
    """Returns the IP address of the host that initiated the request if available."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        ip_str = x_forwarded_for.split(",")[0].strip()
        try:
            return _IPValidator(ip=ip_str).ip  # pyright: ignore[reportArgumentType]
        except ValidationError:
            pass

    if request.client:
        try:
            return _IPValidator(ip=request.client.host).ip  # pyright: ignore[reportArgumentType]
        except ValidationError:
            pass

    return None
