from dataclasses import dataclass

import requests
from temporalio import activity

from apiclient.maas_client import MAASOAuth
from maasserver.models.user import get_creds_tuple


@dataclass
class GetRackControllerInput:
    system_id: str


class MAASAPIActivities:
    def __init__(self, url, token):
        self.url = url
        self.token = token

    @activity.defn(name="get-rack-controller")
    async def get_rack_controller(self, input: GetRackControllerInput):
        url = f"{self.url}/api/2.0/rackcontrollers/{input.system_id}/"
        headers = {}

        oauth = MAASOAuth(*get_creds_tuple(self.token))
        oauth.sign_request(url, headers)
        response = requests.request("GET", url, headers=headers, verify=False)
        response.raise_for_status()

        return response.json()
