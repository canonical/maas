#  Copyright 2023-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.models.base import MaasBaseModel, make_builder


class NodeGroupToRackController(MaasBaseModel):
    uuid: str
    subnet_id: int


NodeGroupToRackControllerBuilder = make_builder(NodeGroupToRackController)
