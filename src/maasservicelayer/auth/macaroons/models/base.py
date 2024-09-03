#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel


class Resource(BaseModel):
    identifier: int
    name: str
