#  Copyright 2023-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine

# SSL modes considered insecure — rejected when hardening is active. Only
# verify-ca / verify-full authenticate the server certificate; require
# encrypts but does not verify, so it is rejected too.
_INSECURE_SSL_MODES = frozenset({"disable", "allow", "prefer", "require"})


@dataclass
class DatabaseConfig:
    name: str
    host: str
    username: str | None = None
    password: str | None = None
    port: int | None = None
    sslmode: str = "prefer"
    sslcert: str = ""
    sslkey: str = ""
    sslrootcert: str = ""

    @property
    def dsn(self) -> URL:
        query: dict[str, str] = {}
        if self.sslmode and self.sslmode != "prefer":
            query["sslmode"] = self.sslmode
        if self.sslcert:
            query["sslcert"] = self.sslcert
        if self.sslkey:
            query["sslkey"] = self.sslkey
        if self.sslrootcert:
            query["sslrootcert"] = self.sslrootcert
        return URL.create(
            "postgresql+asyncpg",
            host=self.host,
            port=self.port,
            database=self.name,
            username=self.username,
            password=self.password,
            query=query,
        )


class InsecureDBSSLModeError(ValueError):
    """Raised when an insecure SSL mode is used with hardening active."""


def build_database_config(
    name: str,
    host: str,
    username: str | None = None,
    password: str | None = None,
    port: int | None = None,
    sslmode: str = "prefer",
    sslcert: str = "",
    sslkey: str = "",
    sslrootcert: str = "",
    hardening_active: bool = False,
) -> DatabaseConfig:
    """Build a ``DatabaseConfig``, enforcing SSL requirements when hardening.

    When *hardening_active* is ``True``, insecure SSL modes (``disable``,
    ``allow``, ``prefer``, ``require``) are rejected with
    ``InsecureDBSSLModeError``; only ``verify-ca``/``verify-full`` are allowed.
    """
    if hardening_active and sslmode in _INSECURE_SSL_MODES:
        raise InsecureDBSSLModeError(
            f"Database SSL mode '{sslmode}' is insecure and not allowed "
            "when hardening is active. Use 'verify-full' or 'verify-ca'."
        )
    return DatabaseConfig(
        name=name,
        host=host,
        username=username,
        password=password,
        port=port,
        sslmode=sslmode,
        sslcert=sslcert,
        sslkey=sslkey,
        sslrootcert=sslrootcert,
    )


class Database:
    def __init__(self, config: DatabaseConfig, echo: bool = False):
        self.config = config
        self.engine = create_async_engine(
            config.dsn,
            echo=echo,
            isolation_level="REPEATABLE READ",
            # Limit the connection pool size to 3 for the time being.
            pool_size=3,
        )
