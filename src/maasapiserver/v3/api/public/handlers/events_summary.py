# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from fastapi import Depends, Header
from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.events_summary import (
    EventsSummaryFiltersParams,
    EventsSummaryMode,
)
from maasapiserver.v3.api.public.models.responses.events_summary import (
    EventsSummaryResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maascommon.openfga.base import MAASResourceEntitlement
from maasserver.config import RegionConfiguration
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.models.events import Event
from maasservicelayer.services import ServiceCollectionV3

_HEADER = [
    "id", "created", "type", "node_system_id", "node_hostname",
    "owner", "action", "description",
]


def _get_ai_config() -> tuple[int, str, str]:
    with RegionConfiguration.open() as config:
        return (
            config.ai_events_max_rows,
            config.ai_events_model,
            config.ai_events_openrouter_url,
        )


def _get_system_prompt(mode: EventsSummaryMode) -> str:
    prompts = {
        EventsSummaryMode.AUDIT: (
            "You are a security auditor. Analyze these MAAS infrastructure event logs. "
            "Focus exclusively on authentication, privilege changes, configuration "
            "modifications, and potential security anomalies. Be forensic and precise."
        ),
        EventsSummaryMode.OPERATIONAL: (
            "You are a Site Reliability Engineer. Analyze these MAAS infrastructure logs. "
            "Focus on machine lifecycle (provisioning, deployment), hardware/driver "
            "failures, and network connectivity. Highlight actionable technical issues."
        ),
        EventsSummaryMode.EXECUTIVE: (
            "You are an executive assistant. Analyze these MAAS logs. "
            "Provide a high-level, non-technical summary of system stability and "
            "major operational trends. Avoid technical jargon."
        ),
        EventsSummaryMode.DEFAULT: (
            "You analyze MAAS infrastructure events. Provide a balanced summary "
            "of system health and notable changes."
        ),
    }
    return prompts.get(mode, prompts[EventsSummaryMode.DEFAULT])


def _get_user_prompt() -> str:
    return (
        "The user message contains tab-separated event data. "
        "Answer from the data only; say if something cannot be determined. "
        "Avoid unnecessary commentary or filler text. Focus on key insights, "
        "trends, and notable events. Start with a title for the summary, "
        "and highlight critical events."
        "\n\n--- Events (tab-separated) ---"
    )


def _to_table(events: list[Event]) -> str:
    rows = [
        [
            str(e.id), str(e.created), e.type.name,
            e.node_system_id or "", e.node_hostname,
            e.owner, e.action, e.description,
        ]
        for e in events
    ]
    return "\n".join(["\t".join(_HEADER)] + ["\t".join(r) for r in rows])


def _call_openrouter(api_key: str, model: str, openrouter_url: str, system_prompt: str, user_prompt: str, table: str) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{user_prompt}\n\n{table}"},
            ],
        }
    ).encode()

    req = Request(
        openrouter_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(req, timeout=120) as resp:
        body = json.load(resp)
    return body["choices"][0]["message"]["content"]


async def _llm_summarize(
    api_key: str, model: str, openrouter_url: str, mode: EventsSummaryMode, table: str
) -> str:
    system_prompt = _get_system_prompt(mode)
    user_prompt = _get_user_prompt()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _call_openrouter, api_key, model, openrouter_url, system_prompt, user_prompt, table
    )


class EventsSummaryHandler(Handler):
    """Events summary API handler."""

    TAGS = ["Events"]

    @handler(
        path="/events/summary",
        methods=["GET"],
        tags=TAGS,
        responses={200: {"model": EventsSummaryResponse}},
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES
                )
            )
        ],
    )
    async def get_events_summary(
        self,
        filters: EventsSummaryFiltersParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        openrouter_api_key: str = Header(alias="x-openrouter-api-key"),  # noqa: B008
    ) -> EventsSummaryResponse:
        max_rows, model, openrouter_url = _get_ai_config()

        # 1. Set End Boundary
        if not filters.created_before:
            filters.created_before = datetime.now(timezone.utc)

        # 3. Fetch Events
        result = await services.events.list(
            page=1,
            size=max_rows,
            query=QuerySpec(where=filters.to_clause()),
        )

        events = result.items
        if filters.created_after:
            events = [e for e in events if e.created >= filters.created_after]
        if filters.created_before:
            events = [e for e in events if e.created <= filters.created_before]

        if not events:
            return EventsSummaryResponse(
                summary="No events found matching the given filters."
            )

        # 4. Summarize via LLM
        summary = await _llm_summarize(
            openrouter_api_key, model, openrouter_url, filters.mode, _to_table(events)
        )
        return EventsSummaryResponse(summary=summary)
