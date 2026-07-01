from cryptography import x509
from cryptography.hazmat.primitives.asymmetric.dsa import DSAPublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.x509.oid import SignatureAlgorithmOID

from maascommon.fips import is_fips_enabled
from maasservicelayer.builders.sslkeys import SSLKeyBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.sslkeys import (
    SSLKeyClauseFactory,
    SSLKeysRepository,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    FIPSViolationException,
)
from maasservicelayer.exceptions.constants import (
    FIPS_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.sslkeys import SSLKey
from maasservicelayer.services.base import BaseService


class SSLKeysService(BaseService[SSLKey, SSLKeysRepository, SSLKeyBuilder]):
    def __init__(
        self,
        context: Context,
        sslkey_repository: SSLKeysRepository,
    ):
        super().__init__(context, sslkey_repository)

    async def pre_create_hook(self, builder: SSLKeyBuilder) -> None:
        # TODO: create a method on the builder to access value only if they are != Unset
        assert isinstance(builder.key, str)

        if is_fips_enabled():
            self._validate_fips_certificate(builder.key)

        sslkey_exists = await self.exists(
            query=QuerySpec(where=SSLKeyClauseFactory.with_key(builder.key))
        )
        if sslkey_exists:
            raise AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message="The SSL key already exist.",
                    )
                ]
            )

    def _validate_fips_certificate(self, key_pem: str) -> None:
        """Validate that a PEM certificate meets FIPS requirements."""
        try:
            cert = x509.load_pem_x509_certificate(key_pem.encode("utf-8"))
        except ValueError:
            # Not a valid PEM certificate; let existing validation handle it
            return

        sig_alg = cert.signature_algorithm_oid
        # Reject SHA-1 and MD5 signatures
        if sig_alg in (
            SignatureAlgorithmOID.RSA_WITH_SHA1,
            SignatureAlgorithmOID.ECDSA_WITH_SHA1,
            SignatureAlgorithmOID.DSA_WITH_SHA1,
            SignatureAlgorithmOID.RSA_WITH_MD5,
        ):
            raise FIPSViolationException(
                details=[
                    BaseExceptionDetail(
                        type=FIPS_VIOLATION_TYPE,
                        message=(
                            f"Certificate signed with {sig_alg._name} is not "
                            "FIPS-compliant. Use SHA-256 or stronger."
                        ),
                    )
                ]
            )
        pub_key = cert.public_key()
        if isinstance(pub_key, DSAPublicKey):
            raise FIPSViolationException(
                details=[
                    BaseExceptionDetail(
                        type=FIPS_VIOLATION_TYPE,
                        message="DSA keys are not FIPS-compliant.",
                    )
                ]
            )
        if isinstance(pub_key, RSAPublicKey):
            key_size = pub_key.key_size
            if key_size < 2048:
                raise FIPSViolationException(
                    details=[
                        BaseExceptionDetail(
                            type=FIPS_VIOLATION_TYPE,
                            message=(
                                f"RSA key size {key_size} bits is below the "
                                "FIPS minimum of 2048 bits."
                            ),
                        )
                    ]
                )

    async def update_by_id(self, id, builder, etag_if_match=None):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_many(self, query, builder):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_one(self, query, builder, etag_if_match=None):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def _update_resource(
        self, existing_resource, builder, etag_if_match=None
    ):
        raise NotImplementedError("Update is not supported for SSL keys")
