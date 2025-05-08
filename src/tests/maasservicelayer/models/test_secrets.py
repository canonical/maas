# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasservicelayer.models.secrets import (
    BMCPowerParametersSecret,
    ClusterCertificateSecret,
    ExternalAuthSecret,
    MAASAutoIPMIKGBmcKeySecret,
    MAASCACertificateSecret,
    MacaroonKeySecret,
    MSMConnectorSecret,
    NodeDeployMetadataSecret,
    NodePowerParametersSecret,
    OMAPIKeySecret,
    RootKeyMaterialSecret,
    RPCSharedSecret,
    SecretForObject,
    SecretModel,
    TLSSecret,
    V3JWTKeySecret,
    VCenterPasswordSecret,
)


class TestSecretModels:
    @pytest.mark.parametrize(
        "model, expected_output",
        [
            (ClusterCertificateSecret(), "global/cluster-certificate"),
            (ExternalAuthSecret(), "global/external-auth"),
            (MAASAutoIPMIKGBmcKeySecret(), "global/ipmi-k_g-key"),
            (MAASCACertificateSecret(), "global/maas-ca-certificate"),
            (MacaroonKeySecret(), "global/macaroon-key"),
            (MSMConnectorSecret(), "global/msm-connector"),
            (OMAPIKeySecret(), "global/omapi-key"),
            (RPCSharedSecret(), "global/rpc-shared"),
            (TLSSecret(), "global/tls"),
            (VCenterPasswordSecret(), "global/vcenter-password"),
            (V3JWTKeySecret(), "global/v3-jwt-key"),
        ],
    )
    def test_get_secret_path_global_models(
        self, model: SecretModel, expected_output: str
    ):
        assert model.get_secret_path() == expected_output

    @pytest.mark.parametrize(
        "model, expected_output",
        [
            (NodeDeployMetadataSecret(id=1), "node/1/deploy-metadata"),
            (NodePowerParametersSecret(id=1), "node/1/power-parameters"),
            (RootKeyMaterialSecret(id=1), "rootkey/1/material"),
            (BMCPowerParametersSecret(id=1), "bmc/1/power-parameters"),
        ],
    )
    def test_get_secret_path_object_models(
        self, model: SecretForObject, expected_output: str
    ):
        assert model.get_secret_path() == expected_output
