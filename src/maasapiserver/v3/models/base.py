from abc import ABC, abstractmethod

from pydantic import BaseModel


class MaasBaseModel(ABC, BaseModel):
    @abstractmethod
    def etag(self) -> str:
        pass
