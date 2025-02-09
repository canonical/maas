# Copyright 2017-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Script handler for the WebSocket connection."""

from maasserver.models import Script
from maasserver.permissions import NodePermission
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class ScriptHandler(TimestampedModelHandler):
    class Meta:
        queryset = Script.objects.all()
        pk = "id"
        allowed_methods = [
            "delete",
            "get_script",
            "list",
        ]
        listen_channels = ["script"]

    def delete(self, params):
        script = self.get_object(params)
        if not self.user.has_perm(NodePermission.admin) or script.default:
            raise HandlerPermissionError()
        script.delete()

    def get_script(self, params):
        id = params.get("id")
        revision = params.get("revision")
        script = self.get_object(params)
        if not script:
            raise HandlerDoesNotExistError(
                f"Script with id({id}) does not exist!"
            )
        if revision:
            for rev in script.script.previous_versions():
                if rev.id == revision:
                    return rev.data
            raise HandlerDoesNotExistError(
                f"Unable to find revision {revision} for {script.name}."
            )
        else:
            return script.script.data
