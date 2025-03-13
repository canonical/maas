# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response
from starlette import status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadRequestBodyResponse,
    ConflictBodyResponse,
    NotFoundBodyResponse,
    NotFoundResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.domains import (
    DNSResourceRecordSetRequest,
    DomainRequest,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.domains import (
    DomainResourceRecordSetListResponse,
    DomainResourceRecordSetResponse,
    DomainResponse,
    DomainsListResponse,
)
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import ServiceCollectionV3


class DomainsHandler(Handler):
    """Domains API handler."""

    TAGS = ["Domains"]

    @handler(
        path="/domains",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": DomainsListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_domains(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        domains = await services.domains.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )
        next_link = None
        if domains.has_next(pagination_params.page, pagination_params.size):
            next_link = f"{V3_API_PREFIX}/domains?{pagination_params.to_next_href_format()}"
        return DomainsListResponse(
            items=[
                DomainResponse.from_model(
                    domain=domain,
                    self_base_hyperlink=f"{V3_API_PREFIX}/domains",
                )
                for domain in domains.items
            ],
            total=domains.total,
            next=next_link,
        )

    @handler(
        path="/domains/{domain_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": DomainResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_domain(
        self,
        domain_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        domain = await services.domains.get_by_id(domain_id)
        if not domain:
            return NotFoundResponse()

        response.headers["ETag"] = domain.etag()
        return DomainResponse.from_model(
            domain=domain, self_base_hyperlink=f"{V3_API_PREFIX}/domains"
        )

    @handler(
        path="/domains",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": DomainResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            409: {"model": ConflictBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_domain(
        self,
        response: Response,
        domain_request: DomainRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        domain = await services.domains.create(domain_request.to_builder())
        response.headers["ETag"] = domain.etag()
        return DomainResponse.from_model(
            domain=domain, self_base_hyperlink=f"{V3_API_PREFIX}/domains"
        )

    @handler(
        path="/domains/{domain_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            400: {"model": BadRequestBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_domain(
        self,
        domain_id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.domains.delete_by_id(domain_id, etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/domains/{domain_id}/rrsets",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": DomainResourceRecordSetListResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_domain_rrsets(
        self,
        domain_id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> DomainResourceRecordSetListResponse:
        assert authenticated_user is not None
        dns_records = await services.v3dnsrrsets.get_dns_records_for_domain(
            domain_id, authenticated_user.id
        )
        return DomainResourceRecordSetListResponse(
            items=[
                DomainResourceRecordSetResponse.from_model(
                    dns_record,
                    self_base_hyperlink=f"{V3_API_PREFIX}/domains/{domain_id}/rrsets",
                )
                for dns_record in dns_records
            ],
            next=None,
            total=len(dns_records),
        )

    @handler(
        path="/domains/{domain_id}/rrsets",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {"model": DomainResourceRecordSetListResponse},
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_domain_rrsets(
        self,
        domain_id: int,
        rrset_request: DNSResourceRecordSetRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> DomainResourceRecordSetResponse:
        assert authenticated_user is not None
        dns_record = rrset_request.to_generic_dns_record()
        await services.v3dnsrrsets.create_dns_records_for_domain(
            domain_id, dns_record, authenticated_user.id
        )
        return DomainResourceRecordSetResponse.from_model(
            dns_record,
            self_base_hyperlink=f"{V3_API_PREFIX}/domains/{domain_id}/rrsets",
        )
