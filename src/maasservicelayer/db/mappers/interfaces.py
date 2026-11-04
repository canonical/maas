# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from pydantic import BaseModel, IPvAnyAddress
from sqlalchemy import desc, Select, select
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.operators import eq

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.mappers.base import StorageRow
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import (
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
)
from maasservicelayer.models.interfaces import Interface, Link


class InterfaceDomainDataMapper(DefaultDomainDataMapper[Interface]):
    def to_domain(self, row: StorageRow) -> Interface:
        if "links" not in row:
            return super().to_domain(row)

        links_by_id = {
            link["id"]: Link(**link)
            for link in row["links"] or []
            if any(link.values())
        }
        values = dict(row)
        values["links"] = sorted(
            links_by_id.values(), key=lambda link: link.id, reverse=True
        )
        return super().to_domain(values)


class InterfaceDetailsDomainDataMapper(InterfaceDomainDataMapper):
    def select_statement(self) -> Select[Any]:
        ip_subquery = (
            select(
                InterfaceIPAddressTable.c.interface_id.label("interface_id"),
                StaticIPAddressTable.c.subnet_id.label("ip_subnet"),
                StaticIPAddressTable.c.id.label("ip_id"),
                StaticIPAddressTable.c.alloc_type.label("ip_type"),
                StaticIPAddressTable.c.ip.label("ip_address"),
            )
            .where(
                eq(
                    InterfaceIPAddressTable.c.staticipaddress_id,
                    StaticIPAddressTable.c.id,
                ),
                StaticIPAddressTable.c.alloc_type != IpAddressType.DISCOVERED,
            )
            .order_by(desc(StaticIPAddressTable.c.id))
            .alias("ip_subquery")
        )

        return (
            select(
                NodeTable.c.id.label("node_id"),
                InterfaceTable.c.id,
                InterfaceTable.c.created,
                InterfaceTable.c.updated,
                InterfaceTable.c.name,
                InterfaceTable.c.type,
                InterfaceTable.c.mac_address,
                InterfaceTable.c.node_config_id,
                InterfaceTable.c.link_connected,
                InterfaceTable.c.interface_speed,
                InterfaceTable.c.enabled,
                InterfaceTable.c.link_speed,
                InterfaceTable.c.sriov_max_vf,
                InterfaceTable.c.vlan_id,
                func.array_agg(
                    func.json_build_object(
                        "id",
                        ip_subquery.c.ip_id,
                        "ip_type",
                        ip_subquery.c.ip_type,
                        "ip_address",
                        ip_subquery.c.ip_address,
                        "ip_subnet",
                        ip_subquery.c.ip_subnet,
                    )
                ).label("links"),
            )
            .select_from(InterfaceTable)
            .join(
                NodeConfigTable,
                eq(NodeConfigTable.c.id, InterfaceTable.c.node_config_id),
                isouter=True,
            )
            .join(
                NodeTable,
                eq(NodeTable.c.current_config_id, NodeConfigTable.c.id),
                isouter=True,
            )
            .join(
                InterfaceIPAddressTable,
                eq(
                    InterfaceTable.c.id, InterfaceIPAddressTable.c.interface_id
                ),
                isouter=True,
            )
            .join(
                ip_subquery,
                eq(ip_subquery.c.interface_id, InterfaceTable.c.id),
                isouter=True,
            )
            .group_by(NodeTable.c.id, InterfaceTable.c.id)
        )


class DiscoveredInterfaceIP(BaseModel):
    ip_subnet: int | None
    ip_address: IPvAnyAddress | None


class DiscoveredInterfaceIPDomainDataMapper(
    DefaultDomainDataMapper[DiscoveredInterfaceIP]
):
    def select_statement(self) -> Select[Any]:
        return (
            select(
                StaticIPAddressTable.c.subnet_id.label("ip_subnet"),
                StaticIPAddressTable.c.ip.label("ip_address"),
            )
            .select_from(NodeTable)
            .where(
                eq(
                    StaticIPAddressTable.c.alloc_type,
                    IpAddressType.DISCOVERED,
                )
            )
            .join(
                NodeConfigTable,
                eq(NodeTable.c.current_config_id, NodeConfigTable.c.id),
                isouter=True,
            )
            .join(
                InterfaceTable,
                eq(NodeConfigTable.c.id, InterfaceTable.c.node_config_id),
                isouter=True,
            )
            .join(
                InterfaceIPAddressTable,
                eq(
                    InterfaceTable.c.id, InterfaceIPAddressTable.c.interface_id
                ),
                isouter=True,
            )
            .join(
                StaticIPAddressTable,
                eq(
                    InterfaceIPAddressTable.c.staticipaddress_id,
                    StaticIPAddressTable.c.id,
                ),
                isouter=True,
            )
            .distinct(StaticIPAddressTable.c.subnet_id)
        )
