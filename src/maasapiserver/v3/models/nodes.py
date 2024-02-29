from maasapiserver.v3.models.base import MaasTimestampedBaseModel


class Node(MaasTimestampedBaseModel):
    # TODO: model to be completed.

    def to_response(self, self_base_hyperlink: str):
        raise Exception("Not implemented yet.")
