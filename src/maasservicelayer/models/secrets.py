# Copyright 2024-2205 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel


class SecretModel(BaseModel, ABC):
    prefix: ClassVar[str]
    secret_name: ClassVar[str]

    @abstractmethod
    def get_secret_path(self) -> str:
        pass


class GlobalSecret(SecretModel):
    prefix = "global"

    def get_secret_path(self):
        return f"{self.prefix}/{self.secret_name}"


class ClusterCertificateSecret(GlobalSecret):
    secret_name = "cluster-certificate"


class ExternalAuthSecret(GlobalSecret):
    secret_name = "external-auth"


class MAASAutoIPMIKGBmcKeySecret(GlobalSecret):
    secret_name = "ipmi-k_g-key"


class MAASCACertificateSecret(GlobalSecret):
    secret_name = "maas-ca-certificate"


class MacaroonKeySecret(GlobalSecret):
    secret_name = "macaroon-key"


class MSMConnectorSecret(GlobalSecret):
    secret_name = "msm-connector"


class OMAPIKeySecret(GlobalSecret):
    secret_name = "omapi-key"


class RPCSharedSecret(GlobalSecret):
    secret_name = "rpc-shared"


class TLSSecret(GlobalSecret):
    secret_name = "tls"


class VCenterPasswordSecret(GlobalSecret):
    secret_name = "vcenter-password"


class V3JWTKeySecret(GlobalSecret):
    secret_name = "v3-jwt-key"


class SecretForObject(SecretModel):
    id: int

    def get_secret_path(self):
        return f"{self.prefix}/{self.id}/{self.secret_name}"


class NodeDeployMetadataSecret(SecretForObject):
    prefix = "node"
    secret_name = "deploy-metadata"


class NodePowerParametersSecret(SecretForObject):
    prefix = "node"
    secret_name = "power-parameters"


class RootKeyMaterialSecret(SecretForObject):
    prefix = "rootkey"
    secret_name = "material"


class BMCPowerParametersSecret(SecretForObject):
    prefix = "bmc"
    secret_name = "power-parameters"


class Secret(BaseModel):
    created: datetime
    updated: datetime
    path: str
    value: Any
