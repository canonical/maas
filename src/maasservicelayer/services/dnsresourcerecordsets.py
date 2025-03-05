#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.models.dnsresourcerecordsets import (
    DNSResourceRecordSet,
    DNSResourceTypeEnum,
)
from maasservicelayer.services.domains import DomainsService


class V3DNSResourceRecordSetsService:
    def __init__(self, domains_service: DomainsService) -> None:
        self.domains_service = domains_service

    async def get_rrsets_for_domain(
        self, domain_id: int, user_id: int | None = None
    ) -> list[DNSResourceRecordSet]:
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
                    DNSResourceRecordSet.from_rrtype(
                        name=hostname,
                        node_id=node_id,
                        ttl=ttl,
                        rrtype=rrtype,
                        rrdatas=rrdatas,
                    )
                )

        return rrsets_for_domain
