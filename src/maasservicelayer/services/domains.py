# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict, OrderedDict
import re
from typing import List

from netaddr import IPAddress

from maascommon.dns import (
    DomainDNSRecord,
    HostnameIPMapping,
    HostnameRRsetMapping,
)
from maascommon.enums.dns import DnsUpdateAction
from maasservicelayer.builders.domains import DomainBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.domains import DomainsRepository
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    NotFoundException,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_DOMAIN_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.configurations import (
    DefaultDnsTtlConfig,
    MAASInternalDomainConfig,
)
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.forwarddnsserver import ForwardDNSServer
from maasservicelayer.models.nodes import Node
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.users import UsersService

# Labels are at most 63 octets long, and a name can be many of them
LABEL = r"[a-zA-Z0-9]([-a-zA-Z0-9]{0,62}[a-zA-Z0-9]){0,1}"
NAMESPEC = rf"({LABEL}[.])*{LABEL}[.]?"


class DomainsService(BaseService[Domain, DomainsRepository, DomainBuilder]):
    def __init__(
        self,
        context: Context,
        configurations_service: ConfigurationsService,
        dnspublications_service: DNSPublicationsService,
        users_service: UsersService,
        domains_repository: DomainsRepository,
    ):
        super().__init__(context, domains_repository)
        self.dnspublications_service = dnspublications_service
        self.configurations_service = configurations_service
        self.users_service = users_service

    async def pre_create_hook(self, builder: DomainBuilder) -> None:
        # Same name validation as maasserver.models.domain.validate_domain_name
        namespec = re.compile(f"^{NAMESPEC}$")
        name = builder.name
        assert isinstance(name, str)
        if len(name) > 255:
            raise ValidationException.build_for_field(
                field="name",
                message="Domain name cannot exceed 255 characters.",
            )
        if not namespec.match(name):
            disallowed_chars = re.sub("[a-zA-Z0-9-.]*", "", name)
            if disallowed_chars:
                raise ValueError("Domain name contains invalid characters.")
            raise ValueError("Invalid domain name.")
        if name == await self.configurations_service.get(
            name=MAASInternalDomainConfig.name
        ):
            raise ValueError(
                "Domain name cannot duplicate MAAS internal domain."
            )

    async def post_create_hook(self, resource: Domain) -> None:
        if resource.authoritative:
            await self.dnspublications_service.create_for_config_update(
                source=f"added zone {resource.name}",
                action=DnsUpdateAction.RELOAD,
            )

    async def post_update_hook(
        self, old_resource: Domain, updated_resource: Domain
    ) -> None:
        source = None
        if old_resource.authoritative and not updated_resource.authoritative:
            source = f"removed zone {updated_resource.name}"
        elif not old_resource.authoritative and updated_resource.authoritative:
            source = f"added zone {updated_resource.name}"
        elif old_resource.authoritative and updated_resource.authoritative:
            changes = []
            if old_resource.name != updated_resource.name:
                changes.append(f"renamed to {updated_resource.name}")
            if old_resource.ttl != updated_resource.ttl:
                changes.append(f"ttl changed to {updated_resource.ttl}")
            if changes:
                source = f"zone {old_resource.name} " + " and ".join(changes)

        if source:
            await self.dnspublications_service.create_for_config_update(
                source=source,
                action=DnsUpdateAction.RELOAD,
            )

    async def post_update_many_hook(self, resources: List[Domain]) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def pre_delete_hook(self, resource_to_be_deleted: Domain) -> None:
        default_domain = await self.get_default_domain()
        if resource_to_be_deleted.id == default_domain.id:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=CANNOT_DELETE_DEFAULT_DOMAIN_VIOLATION_TYPE,
                        message="The default domain cannot be deleted.",
                    )
                ]
            )

    async def post_delete_hook(self, resource: Domain) -> None:
        if resource.authoritative:
            await self.dnspublications_service.create_for_config_update(
                source=f"removed zone {resource.name}",
                action=DnsUpdateAction.RELOAD,
            )

    async def post_delete_many_hook(self, resources: List[Domain]) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def get_default_domain(self) -> Domain:
        return await self.repository.get_default_domain()

    async def get_hostname_ip_mapping(
        self,
        domain_id: int | None = None,
        raw_ttl: bool = False,
        with_node_id: bool = False,
    ) -> dict[str, HostnameIPMapping]:
        default_ttl = await self.configurations_service.get(
            name=DefaultDnsTtlConfig.name
        )
        return await self.repository.get_hostname_ip_mapping(
            default_ttl, domain_id, raw_ttl, with_node_id
        )

    async def get_hostname_dnsdata_mapping(
        self,
        domain_id: int,
        raw_ttl=False,
        with_ids=True,
        with_node_id: bool = False,
    ) -> dict[str, HostnameRRsetMapping]:
        default_ttl = await self.configurations_service.get(
            name=DefaultDnsTtlConfig.name
        )
        return await self.repository.get_hostname_dnsdata_mapping(
            domain_id, default_ttl, raw_ttl, with_ids, with_node_id
        )

    async def v3_render_json_for_related_rrdata(
        self,
        domain_id: int,
        user_id: int | None = None,
        include_dnsdata=True,
        as_dict=False,
        with_node_id=False,
    ) -> OrderedDict[str, list[DomainDNSRecord]] | list[DomainDNSRecord]:
        """Render a representation of a domain's related non-IP data,
        suitable for converting to JSON.

        NOTE: This has been moved from src/maasserver/models/domain.py and the
        relative tests are still in src/maasserver/models/tests/test_domain.py

        The v3 variant of this method just adds the node_id to the result and
        modifies the result type. In order to not change the API contract in v2,
        use `render_json_for_related_rrdata` below.

        Params:
            domain_id: The domain to calculate dns resources for
            user_id: Restrict the data to what the user can see
            include_dnsdata: Whether to include dns data or not
            as_dict: Whether to return the data as a dict or as a list
        """

        domain = await self.get_by_id(domain_id)
        if domain is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Domain with id {domain_id} does not exist.",
                    )
                ]
            )

        if user_id is not None:
            user = await self.users_service.get_by_id(user_id)
            if user is None:
                raise NotFoundException(
                    details=[
                        BaseExceptionDetail(
                            type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                            message=f"User with id {user_id} does not exist.",
                        )
                    ]
                )
        else:
            user = None

        if include_dnsdata is True:
            rr_mapping = await self.get_hostname_dnsdata_mapping(
                domain_id, raw_ttl=True, with_node_id=with_node_id
            )
        else:
            rr_mapping = defaultdict(HostnameRRsetMapping)
        # Smash the IP Addresses in the rrset mapping, so that the far end
        # only needs to worry about one thing.
        ip_mapping = await self.get_hostname_ip_mapping(
            domain_id, raw_ttl=True, with_node_id=with_node_id
        )
        for hostname, info in ip_mapping.items():
            if (
                user is not None
                and not user.is_superuser
                and info.user_id is not None
                and info.user_id != user.id
            ):
                continue
            entry = rr_mapping[hostname[: -len(domain.name) - 1]]
            entry.dnsresource_id = info.dnsresource_id
            if info.system_id is not None:
                entry.system_id = info.system_id
                entry.node_type = info.node_type
                if with_node_id:
                    entry.node_id = info.node_id
            if info.user_id is not None:
                entry.user_id = info.user_id
            for ip in info.ips:
                record_type = (
                    "AAAA" if IPAddress(str(ip)).version == 6 else "A"
                )
                entry.rrset.add((info.ttl, record_type, ip, None))
        if as_dict:
            result = OrderedDict()
        else:
            result = []
        for hostname, info in rr_mapping.items():
            data = [
                DomainDNSRecord(
                    name=hostname,
                    system_id=info.system_id,
                    node_type=info.node_type,
                    user_id=info.user_id,
                    dnsresource_id=info.dnsresource_id,
                    node_id=info.node_id,
                    ttl=ttl,
                    rrtype=rrtype,
                    rrdata=rrdata,
                    dnsdata_id=dnsdata_id,
                )
                for ttl, rrtype, rrdata, dnsdata_id in info.rrset
                if (
                    info.user_id is None
                    or user is None
                    or user.is_superuser
                    or (info.user_id is not None and info.user_id == user.id)
                )
            ]
            if isinstance(result, OrderedDict):
                existing = result.get(hostname, [])
                existing.extend(data)
                result[hostname] = existing
            else:
                result.extend(data)
        return result

    async def render_json_for_related_rrdata(
        self,
        domain_id: int,
        user_id: int | None = None,
        include_dnsdata=True,
        as_dict=False,
    ) -> OrderedDict[str, list[dict]] | list[dict]:
        result = await self.v3_render_json_for_related_rrdata(
            domain_id, user_id, include_dnsdata, as_dict
        )
        if isinstance(result, dict):
            return OrderedDict(
                {
                    key: [v.to_dict(with_node_id=False) for v in values]
                    for key, values in result.items()
                }
            )
        else:
            return [v.to_dict(with_node_id=False) for v in result]

    async def get_forwarded_domains(
        self,
    ) -> List[tuple[Domain, ForwardDNSServer]]:
        return await self.repository.get_forwarded_domains()

    async def get_domain_for_node(self, node: Node) -> Domain:
        if node.domain_id:
            result = await self.repository.get_by_id(node.domain_id)
        else:
            result = await self.get_default_domain()

        assert result is not None
        return result
