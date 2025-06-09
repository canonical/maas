#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

from maascommon.enums.dns import DNSResourceTypeEnum
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.builders.dnsdata import DNSDataBuilder
from maasservicelayer.builders.dnsresources import DNSResourceBuilder
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsdata import DNSDataClauseFactory
from maasservicelayer.db.repositories.dnsresources import (
    DNSResourceClauseFactory,
)
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.dnsresourcerecordsets import GenericDNSRecord
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.services.base import Service
from maasservicelayer.services.dnsdata import DNSDataService
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService


class V3DNSResourceRecordSetsService(Service):
    def __init__(
        self,
        context: Context,
        domains_service: DomainsService,
        dnsresource_service: DNSResourcesService,
        dnsdata_service: DNSDataService,
        staticipaddress_service: StaticIPAddressService,
        subnets_service: SubnetsService,
    ) -> None:
        super().__init__(context)
        self.domains_service = domains_service
        self.dnsresource_service = dnsresource_service
        self.dnsdata_service = dnsdata_service
        self.staticipaddress_service = staticipaddress_service
        self.subnets_service = subnets_service

    async def get_dns_records_for_domain(
        self, domain_id: int, user_id: int | None = None
    ) -> list[GenericDNSRecord]:
        rrsets_for_domain = []
        rrsets_dict = (
            await self.domains_service.v3_render_json_for_related_rrdata(
                domain_id, user_id, as_dict=True, with_node_id=True
            )
        )

        assert isinstance(rrsets_dict, dict)
        for hostname, rrsets_list in rrsets_dict.items():
            # filter for each rrtype
            for rrtype in DNSResourceTypeEnum:
                rrsets = [
                    rrset
                    for rrset in rrsets_list
                    if rrset.rrtype == rrtype.value
                ]
                if len(rrsets) == 0:
                    continue
                # the node_id and ttl are the same for the same hostname
                node_id = rrsets[0].node_id
                ttl = rrsets[0].ttl
                rrdatas = [rrset.rrdata for rrset in rrsets]
                rrsets_for_domain.append(
                    GenericDNSRecord(
                        name=hostname,
                        node_id=node_id,
                        ttl=ttl,
                        rrtype=rrtype,
                        rrdatas=rrdatas,
                    )
                )

        return rrsets_for_domain

    async def create_dns_records_for_domain(
        self, domain_id: int, dns_record: GenericDNSRecord, user_id: int
    ) -> None:
        """Creates a DNS resource record for the specified domain.

        Our data model treats A, AAAA resource records differently.
        For all the other types, we have a container that is dnsresource and
        the single records that are dnsdata.
        For A and AAAA records, instead, we don't have a dnsdata entry, but we
        have a link between dnsresource and staticipaddress. So when creating this
        kind of DNS resource we have to worry of also creating (if necessary)
        all the needed staticipaddress that must be reserved by the user issuing
        the request.
        """
        domain = await self.domains_service.get_by_id(domain_id)
        if domain is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Domain with id {domain_id} does not exist.",
                    )
                ]
            )

        dns_resource = await self.dnsresource_service.get_one(
            query=QuerySpec(
                where=DNSResourceClauseFactory.and_clauses(
                    [
                        DNSResourceClauseFactory.with_name(dns_record.name),
                        DNSResourceClauseFactory.with_domain_id(domain_id),
                    ]
                )
            )
        )

        if dns_record.rrtype in (
            DNSResourceTypeEnum.A,
            DNSResourceTypeEnum.AAAA,
        ):
            await self._create_a_aaaa_records_for_domain(
                dns_record=dns_record,
                user_id=user_id,
                domain=domain,
                dns_resource=dns_resource,
            )
        else:
            await self._create_dnsdata_records_for_domain(
                dns_record=dns_record, domain=domain, dns_resource=dns_resource
            )

    async def _create_a_aaaa_records_for_domain(
        self,
        dns_record: GenericDNSRecord,
        user_id: int,
        domain: Domain,
        dns_resource: DNSResource | None,
    ) -> None:
        if dns_resource is None:
            ttl = dns_record.ttl or domain.ttl
            dns_resource = await self.dnsresource_service.create(
                DNSResourceBuilder(
                    name=dns_record.name,
                    address_ttl=ttl,
                    domain_id=domain.id,
                )
            )
        else:
            if dns_record.ttl is not None:
                await self.dnsresource_service.update_by_id(
                    id=dns_resource.id,
                    builder=DNSResourceBuilder(address_ttl=dns_record.ttl),
                )
        for ip_address in dns_record.rrdatas:
            ip_address = (
                IPv4Address(ip_address)
                if dns_record.rrtype == DNSResourceTypeEnum.A
                else IPv6Address(ip_address)
            )
            static_ip_addr = await self.staticipaddress_service.get_one(
                query=QuerySpec(
                    where=StaticIPAddressClauseFactory.with_ip(ip_address)
                )
            )
            if static_ip_addr is None:
                subnet = await self.subnets_service.find_best_subnet_for_ip(
                    ip_address
                )
                # Here subnet could be None. We create the IP anyway as the
                # subnet could be not managed by MAAS.
                static_ip_addr = await self.staticipaddress_service.create(
                    StaticIPAddressBuilder(
                        ip=ip_address,  # pyright: ignore [reportArgumentType]
                        alloc_type=IpAddressType.USER_RESERVED,
                        user_id=user_id,
                        subnet_id=subnet.id if subnet is not None else None,
                        lease_time=0,
                    )
                )
            await self.dnsresource_service.link_ip(
                dnsrr_id=dns_resource.id, ip_id=static_ip_addr.id
            )

    async def _create_dnsdata_records_for_domain(
        self,
        dns_record: GenericDNSRecord,
        domain: Domain,
        dns_resource: DNSResource | None,
    ) -> None:
        if dns_resource is None:
            dns_resource = await self.dnsresource_service.create(
                DNSResourceBuilder(name=dns_record.name, domain_id=domain.id)
            )
        ttl = dns_record.ttl or domain.ttl
        cname_exists = await self.dnsdata_service.exists(
            query=QuerySpec(
                where=DNSDataClauseFactory.and_clauses(
                    [
                        DNSDataClauseFactory.with_dnsresource_id(
                            dns_resource.id
                        ),
                        DNSDataClauseFactory.with_rrtype(
                            DNSResourceTypeEnum.CNAME
                        ),
                    ]
                )
            )
        )
        if cname_exists:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="Cannot create DNS record. A CNAME exists for this name.",
                    )
                ]
            )
        if dns_record.rrtype == DNSResourceTypeEnum.CNAME:
            # Since dns records could be in two different places, we have to check
            # both the dnsdata and the IPs
            other_exists = await self.dnsdata_service.exists(
                query=QuerySpec(
                    where=DNSDataClauseFactory.and_clauses(
                        [
                            DNSDataClauseFactory.with_dnsresource_id(
                                dns_resource.id
                            ),
                            DNSDataClauseFactory.not_clause(
                                DNSDataClauseFactory.with_rrtype(
                                    DNSResourceTypeEnum.CNAME
                                )
                            ),
                        ]
                    )
                )
            )
            if not other_exists:
                ips_exists = (
                    await self.dnsresource_service.get_ips_for_dnsresource(
                        dns_resource.id
                    )
                )
                other_exists = bool(len(ips_exists))
            if other_exists:
                raise BadRequestException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_ARGUMENT_VIOLATION_TYPE,
                            message="CNAME records for a name cannot coexist with non-CNAME records.",
                        )
                    ]
                )
        for rrdata in dns_record.rrdatas:
            await self.dnsdata_service.create(
                DNSDataBuilder(
                    dnsresource_id=dns_resource.id,
                    ttl=ttl,
                    rrtype=dns_record.rrtype,
                    rrdata=rrdata,
                )
            )
