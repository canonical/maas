#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from netaddr import IPAddress

from maasapiserver.v3.api.public.models.responses.interfaces import (
    InterfaceResponse,
    InterfaceTypeEnum,
    LinkResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasserver.enum import IPADDRESS_TYPE
from maasservicelayer.models.interfaces import Interface, Link
from maasservicelayer.utils.date import utcnow

link = Link(
    id=1,
    ip_type=IPADDRESS_TYPE.AUTO,
    ip_address=IPAddress(addr="10.10.10.10"),
    ip_subnet=0,
)


class TestLinkResponse:
    def test_to_respone(self) -> None:

        response = LinkResponse.from_model(link)
        assert response.id == link.id
        assert response.ip_address == link.ip_address
        assert response.mode == link.mode


class TestInterfaceModel:
    def test_from_model(self) -> None:
        now = utcnow()
        interface = Interface(
            id=1,
            created=now,
            updated=now,
            name="test_interface",
            type=InterfaceTypeEnum.physical,
            mac_address="",
            link_connected=True,
            interface_speed=0,
            link_speed=0,
            sriov_max_vf=0,
            links=[link],
        )
        response = InterfaceResponse.from_model(
            interface=interface,
            self_base_hyperlink=f"{V3_API_PREFIX}/machines/1/interfaces",
        )
        assert response.id == interface.id
        assert response.name == interface.name
        assert response.type == interface.type
        assert response.mac_address == interface.mac_address
        assert response.link_connected == interface.link_connected
        assert response.interface_speed == interface.interface_speed
        assert response.enabled == interface.enabled
        assert response.link_speed == interface.link_speed
        assert response.sriov_max_vf == interface.sriov_max_vf
        assert response.links == [
            LinkResponse.from_model(link) for link in interface.links
        ]
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/machines/1/interfaces/{interface.id}"
        )
