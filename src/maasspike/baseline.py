from maasserver.websockets.handlers.machine import MachineHandler


class NoPaginationMachineHandler(MachineHandler):
    """A machine handler that returns only the machines.

    It doesn't do any grouping, searching, or other things
    (like caching the ids) which might slow it down.

    The purpose of this is to use our current implementation as a baseline
    for other implementations to beat. We reuse the current websocket
    handler as much as possible, so that any improvements to it will
    be shown here as well.
    """

    def list(self, params):
        qs = self.get_queryset(for_list=True)
        qs = self._sort(qs, "list", params)
        limit = params.get("limit")
        if limit:
            qs = qs[:limit]
        objs = list(qs)
        # This is needed to calculate the script result summaries.
        # It's quite expensive.
        self._cache_script_results(objs)
        return [self.full_dehydrate(obj, for_list=True) for obj in objs]


def list_machines(admin, limit=None):
    ws_handler = NoPaginationMachineHandler(admin, {}, None)
    params = {}
    if limit:
        params["limit"] = limit
    return ws_handler.list(params)
