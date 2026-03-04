# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.models.base import MaasBaseModel


class UserGroupMember(MaasBaseModel):
    group_id: int
    username: str
    email: str
