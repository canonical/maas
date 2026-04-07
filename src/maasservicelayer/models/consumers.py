# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.models.base import generate_builder, MaasBaseModel


@generate_builder()
class Consumer(MaasBaseModel):
    name: str
    description: str
    key: str
    secret: str
    status: str
    user_id: int | None = None
