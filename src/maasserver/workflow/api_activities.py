from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession
import requests
from temporalio import activity

from apiclient.maas_client import MAASOAuth
from maasserver.models.user import get_creds_tuple


@dataclass
class GetRackControllerInput:
    system_id: str


@dataclass
class SwitchBootOrderInput:
    system_id: str
    network_boot: bool


class MAASAPIClient:
    def __init__(self, url: str, token):
        self._url = url.rstrip("/")
        self._oauth = MAASOAuth(*get_creds_tuple(token))

    async def ainternal_request(
        self, method: str, url: str, data: dict[str, Any] = None
    ):
        headers = {}
        self._oauth.sign_request(url, headers)
        async with ClientSession(headers=headers) as session:
            async with session.request(
                method, url, verify_ssl=False, data=data
            ) as response:
                response.raise_for_status()
                return await response.json()

    def _internal_request(
        self, method: str, url: str, data: dict[str, Any] = None
    ):
        headers = {}

        self._oauth.sign_request(url, headers)
        response = requests.request(
            method,
            url,
            headers=headers,
            verify=False,
            data=data,
            proxies={"http": "", "https": ""},
        )
        response.raise_for_status()

        return response.json()


class MAASAPIActivities(MAASAPIClient):
    @activity.defn(name="get-rack-controller")
    async def get_rack_controller(self, input: GetRackControllerInput):
        url = f"{self._url}/api/2.0/rackcontrollers/{input.system_id}/"
        return self._internal_request("GET", url)

    @activity.defn(name="switch-boot-order")
    async def switch_boot_order(self, input: SwitchBootOrderInput):
        url = f"{self._url}/api/2.0/switch-boot-order/{input.system_id}/"
        return self._internal_requests(
            "PUT",
            url,
            data={
                "network_boot": input.network_boot,
            },
        )
